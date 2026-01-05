import datetime
import os.path
from typing import Optional, Tuple

import numpy as np
import pandas as pd

from utils.agency import standardize_agency_name
from utils.cdr.columns import rename_columns, sort_columns
from utils.config import load_config
from utils.data import (clean_floats, 
                        convert_date_cols, 
                        convert_df,
                        dedup_cdr_by_col,
                        fix_coroner,
                        fix_other_behavior,
                        merge_dupes,
                        reorder_columns_and_check,
                        standardize_gender_cols, 
                        standardize_race_cols, 
                        upcase_strip_string_cells)
from utils.logger import LOGGER
from utils.s3 import get_s3_data, save_s3
from utils.secrets import get_secret
from utils.sheets import retrieve_sheet

RANGES: list = ["2016", "2005"]

# TODO: figure out how to abort if sheet has not been updated since last run
def main():
    config: dict = get_secret(['sheets', 's3', 'cdr'])
    
    # CDR: load reference data sets
    LOGGER.debug('Loading auxilliary datasets')
    master_2017: pd.DataFrame = get_s3_data('tji-static-datasets', 'reformatted_cdr_2017_master_file.csv')

    agency_county: pd.DataFrame = get_s3_data('tji-static-datasets', 'agencies_and_counties.csv')
    agency_county = agency_county.set_index('agency')['county'].to_dict()

    # TODO: make doc type param
    doc_config: dict = config.get('cdr', {})

    # retrieve data from both sheets needed for CDR
    # TODO: store range info in config
    cdr: pd.DataFrame = pd.DataFrame() # match to notebook because laziness
    for range_name in RANGES:
        doc_config['range_name'] = f"Form Version {range_name}"

        sheet_data: Optional[Tuple[list, list]] = retrieve_sheet(config.get('sheets', {}), doc_config)

        if sheet_data is not None:
            header, rows = sheet_data
            df: pd.DataFrame = convert_df(header, rows)
            df['form_version'] = f"V_{range_name}"
            df.to_csv(f"{range_name}_cdr.csv", index=False)
        
            cdr = pd.concat([cdr, df])

    LOGGER.debug(f"CDR data downloaded from Google Sheets. Dataframe shape: {cdr.shape}")

    # TODO: what is this for?
    # cdr.groupby(['Specific Type of Custody/Facility', 'Street Address', 'TDCJ - Specify Unit'], dropna=False)['CDR: CDR Name'].count().to_csv('cdr_unit_data.csv')
    
    # dataset-specific cleaning - output to clean dataset bucket

    ## for CDR -----------------------------------------------------------------------
    # confirm no null date fields:
    # TODO: move invalid data to invalid data file instead of breaking all the things
    assert cdr['Death Date and Time'].isnull().sum() == 0

    LOGGER.debug(f"CDR df shape: {cdr.shape}")

    ### set death datetime to correct type
    ### TODO: UserWarning: Could not infer format; To ensure parsing is consistent and as-expected, please specify a format.
    cdr['Death Date and Time'] = pd.to_datetime(cdr['Death Date and Time'])

    ### drop data before 2005
    cdr = cdr[cdr['Death Date and Time'].dt.year >= 2005]

    LOGGER.debug(f"CDR df shape: {cdr.shape}")

    ### drop unused columns, rename others
    OTHER_SPECIFY = 'OTHER, SPECIFY' # TODO: consolidate these somewhere
    keep = sort_columns()
    renames: dict = rename_columns(keep)

    cdr = cdr[list(renames.keys())]
    cdr.rename(columns=renames, inplace=True)

    LOGGER.debug(f"CDR df shape: {cdr.shape}")

    ### Add reference_data:2017_master_file data
    master_2017['form_version'] = 'V_BJS'

    ## CHECK: master file doesn't have any columns not in current dataset
    #### TODO: Ask if this may need to blow up processing or can those rows just go to a problem rows files?
    LOGGER.debug(f"OLD: {master_2017.shape} CDR: {cdr.shape}")
    assert len(set(master_2017.columns) - set(cdr.columns)) == 0
    
    ## MERGE
    cdr = pd.concat([cdr, master_2017])
    cdr.reset_index(inplace=True, drop=True)
    cdr.sort_values('form_version', inplace=True)

    ### column type conversions/cleanup
    s1 = cdr.dtypes
    cdr = convert_date_cols(cdr)

    s2 = cdr.dtypes
    different = s1[s1 != s2].index.tolist()
    LOGGER.debug("Changed %d cols to datetime (from some other dtype):" % len(different), different)

    ### clean floats
    float_cols = [
    'age_at_time_of_death',
    'agency_zip',
    'custody_date_na',
    'entry_date_time_n_a',
    'version_number'
    ]
    cdr = clean_floats(cdr, float_cols)
    ### upcase string columns
    cdr = upcase_strip_string_cells(cdr)

    ### make death_date column
    cdr['death_date'] = pd.to_datetime(cdr.death_date_and_time.apply(lambda dt: datetime.date(dt.year, dt.month, dt.day)))
    
    ### standardize columns/formats
    
    ### race/ethnicity
    cdr.loc[cdr.ethnicity.fillna('').str.contains('OTHER'), 'ethnicity'] = 'OTHER'
    cdr.loc[cdr.ethnicity_other.astype(str) == '0', 'ethnicity_other'] = None # 2005 form has description field for "OTHER"

    other_eth = (cdr.ethnicity == 'OTHER')
    LOGGER.info('Merging %d "ethnicity_other" values into the main "ethnicity" column' % other_eth.sum())
    cdr.loc[other_eth, 'ethnicity'] = cdr.ethnicity_other[other_eth]
    cdr.drop('ethnicity_other', axis=1, inplace=True)

    # Make a single 'race' column that has merged, simplified values of race or ethnicity.
    race_eth_list = []
    for race, eth in zip(cdr.race, cdr.ethnicity):
        # Only one of (race, eth) should be set
        assert pd.isnull(race) or pd.isnull(eth)
        if pd.isnull(race):
            if pd.isnull(eth):
                race_eth_list.append(None)
                continue
            x = eth
        else:
            x = race
        race_eth_list.append(x)
    
    cdr['race'] = race_eth_list
    cdr.drop('ethnicity', axis=1, inplace=True)

    cdr = standardize_race_cols(cdr)

    ### agency info
    # Standardize agency name (so we can join/compare across datasets)
    cdr['agency_name'] = cdr['agency_name'].apply(standardize_agency_name)

    # Lookup county name by agency name. If this fails, fall back
    # on the county specified in the form, if it exists.
    cdr['agency_county'] = cdr['agency_county'].str.upper()
    county_lookup = cdr['agency_name'].apply(lambda name: agency_county.get(name, np.nan))
    cdr['agency_county'] = county_lookup.fillna(cdr['agency_county'])

    # Manually handle one major agency
    cdr.loc[cdr['agency_name'] == 'TEXAS DEPT OF CRIMINAL JUSTICE', 'agency_county'] = 'STATE'

    # Clearly 'TEST CDR AGENCY' is meant to be ignored
    test_agencies = cdr['agency_name'] == 'TEST CDR AGENCY'
    cdr = cdr[~test_agencies]
    LOGGER.info("Dropping %d records from 'TEST CDR AGENCY', leaving %d records" % (test_agencies.sum(), len(cdr)))
    
    ### death details (lots of columns here)
    cdr['death_location'] = np.where(cdr['death_location'].isin([0,1]),
                                    np.nan,
                                    cdr['death_location'])

    replacements = {
        'AT MEDICAL FACILITY': 'MEDICAL FACILITY',
        'AT LAW ENFORCEMENT FACILITY': 'LAW ENFORCEMENT FACILITY',
        'AT THE CRIME/ARREST SCENE': 'CRIME/ARREST SCENE',
        'SCENE OF INCIDENT': 'CRIME/ARREST SCENE',
        'LAW ENFORCEMENT FACILITY/BOOKING CENTER': 'LAW ENFORCEMENT FACILITY',
        'DEAD ON ARRIVAL AT MEDICAL FACILITY': 'EN ROUTE TO MEDICAL FACILITY',
        'EN ROUTE TO BOOKING CENTER/POLICE LOCKUP': 'EN ROUTE TO LAW ENFORCEMENT FACILITY',
        'ELSEWHERE': OTHER_SPECIFY,
        'ELSEWHERE, SPECIFY': OTHER_SPECIFY,
    }
    cdr['death_location'] = cdr['death_location'].apply(lambda x: None if pd.isnull(x) else replacements.get(x.strip(), x))

    replacements = {
    'NOT APPLICABLE, CAUSE OF DEATH WAS ILLNESS/NATURAL CAUSE': 'NOT APPLICABLE',
    'NOT APPLICABLE; CAUSE OF DEATH WAS INTOXICATION OR ILLNESS/NATURAL CAUSES': 'NOT APPLICABLE',
    'OTHER': OTHER_SPECIFY,
    'KNIFE, CUTTING INSTRUMENT': 'KNIFE / EDGED INSTRUMENT',
    'BLUNT INSTRUMENT': 'BATON / BLUNT INSTRUMENT',
    "DON'T KNOW": 'UNKNOWN',
    "DON\\'T KNOW": 'UNKNOWN',
    'RIFLE/SHOTGUN': 'FIREARM',
}
    cdr['means_of_death'] = cdr['means_of_death'].apply(lambda x:  None if pd.isnull(x) else replacements.get(x.strip(), x))

    cdr[cdr.means_of_death == OTHER_SPECIFY]['means_of_death_other'].value_counts().head()

    other_values = ['UNKNOWN', 'VEHICLE ACCIDENT', 'KNIFE / EDGED INSTRUMENT', 'BATON / BLUNT INSTRUMENT']
    indices = cdr['means_of_death'].isin(other_values)
    cdr.loc[indices, 'means_of_death_other'] = cdr.loc[indices, 'means_of_death']
    cdr.loc[indices, 'means_of_death'] = OTHER_SPECIFY

    replacements = {
        'NATURAL': 'NATURAL CAUSES/ILLNESS',
        'JUSTIFIABLE HOMICIDE': 'HOMICIDE',
        'HOMICIDE BY LAW ENFORCEMENT/CORRECTIONAL STAFF': 'HOMICIDE',
        'OTHER HOMICIDE': 'HOMICIDE',
        'HOMICIDE (INCLUDES JUSTIFIABLE HOMICIDE)': 'HOMICIDE',
        'ACCIDENTAL INJURY CAUSED BY OTHERS': 'ACCIDENTAL',
        'ACCIDENTAL INJURY TO SELF': 'ACCIDENTAL',
        'OTHER': OTHER_SPECIFY,
        'OTHER - SPECIFY': OTHER_SPECIFY,
    }
    cdr['manner_of_death'] = cdr['manner_of_death'].apply(lambda x: None if pd.isnull(x) else replacements.get(x.strip(), x))

    # In past versions, "pending autopsy results" was not an option, and reports had "other"
    # checked with some mention of pending autopsy in the free field. We emulate this here
    # to preserve consistency across form versions.
    other_values = ['PENDING AUTOPSY RESULTS', 'COULD NOT BE DETERMINED']
    indices = cdr['manner_of_death'].isin(other_values)
    cdr.loc[indices, 'manner_of_death_description'] = cdr.loc[indices, 'manner_of_death']
    cdr.loc[indices, 'manner_of_death'] = OTHER_SPECIFY

    frame = cdr[(cdr.manner_of_death == 'SUICIDE') & (cdr.means_of_death != 'HANGING, STRANGULATION')]
    frame = frame[(frame.medical_cause_of_death.fillna('').str.contains('HANGING')) |
                frame.manner_of_death_description.fillna('').str.contains('HANGING')]

    cdr.loc[frame.index, 'means_of_death'] = 'HANGING, STRANGULATION'

    # Be sure we got them all
    frame = cdr[(cdr.manner_of_death == 'SUICIDE') & (cdr.means_of_death != 'HANGING, STRANGULATION')]
    frame = frame[frame.medical_cause_of_death.fillna('').str.contains('HANGING')]
    assert len(frame) == 0

    frame = cdr[(cdr.manner_of_death == 'SUICIDE') & (cdr.means_of_death == 'NOT APPLICABLE')]
    cdr.loc[frame.index, 'means_of_death'] = OTHER_SPECIFY
    assert len(cdr[(cdr.manner_of_death == 'SUICIDE') & (cdr.means_of_death == 'NOT APPLICABLE')]) == 0

    replacements = {
        'DECEASED DEVELOPED CONDITION AFTER ADMISSION': 'DEVELOPED CONDITION AFTER ADMISSION',
        "DON'T KNOW": 'UNKNOWN',
        "DON\\'T KNOW": 'UNKNOWN',
        'NOT APPLICABLE; CAUSE OF DEATH WAS ACCIDENTAL INJURY, INTOXICATION, SUICIDE OR HOMICIDE': 'NOT APPLICABLE',
        'COULD NOT BE DETERMINED': 'UNKNOWN',
        'PRE-EXISTING MEDICAL CONDITION': 'YES',
    }
    cdr['pre_existing_medical_condition'] = cdr['pre_existing_medical_condition'].apply(lambda x: None if pd.isnull(x) else replacements.get(x.strip(), x))
    
    ### who caused death
    """
    NOTE: This question is framed as follows:
    * 2005 form: "If the death was an accident or homicide, who caused the death?"
    * 2016 form: "If the death was an accident, homicide **or suicide**, who caused the death?" (emphasis added)

    Thus, we need to:
    1. Collapse near-identical values from different forms, similar to the other areas here.
    1. Remove suicides from the 2016 responses, as they skew the data. While we're at it, change ANY entries that are not of type homicide/suicide to have "NOT APPLICABLE" as the value.
    """

    replacements = {
    'DECEASED': 'DECEDENT',
    "DON'T KNOW": 'UNKNOWN',
    "DON\\'T KNOW": 'UNKNOWN',
    'LAW ENFORCEMENT/CORRECTIONAL STAFF': 'LAW ENFORCEMENT/CORRECTIONAL PERSONNEL',
    'NOT APPLICABLE; CAUSE OF DEATH WAS SUICIDE, INTOXICATION OR ILLNESS/NATURAL CAUSES': 'NOT APPLICABLE',
    'OTHER DETAINEES': 'OTHER DETAINEE(S)',
    'OTHER PERSONS': 'OTHER CIVILIAN(S)',
    'ACCIDENTAL INJURY TO SELF': 'ACCIDENTAL',
    'UNKNOWN PERSON(S) CAUSED THE INJURY': 'UNKNOWN',
    'UNKNOWN WHETHER DECEDENT SUSTAINED A FATAL INJURY': 'UNKNOWN',
}
    cdr['who_caused_the_death'] = cdr['who_caused_the_death'].apply(lambda x:  None if pd.isnull(x) else replacements.get(x.strip(), x))
    cdr.loc[~cdr.manner_of_death.isin(['HOMICIDE', 'ACCIDENTAL', OTHER_SPECIFY]), 'who_caused_the_death'] = 'NOT APPLICABLE'

    cdr['medical_examinor_coroner_evalution'] = cdr['medical_examinor_coroner_evalution'].apply(fix_coroner)  

    ### gender
    cdr = standardize_gender_cols(cdr)

    ### were there charges
    replacements = {
        'CAPITAL MURDER': 'CONVICTED',
        'PROBATION/PAROLE': 'PROBATION/PAROLE VIOLATION',
        'A PROBATION/PAROLE VIOLATION': 'PROBATION/PAROLE VIOLATION',
    }
    cdr['were_the_charges'] = cdr['were_the_charges'].apply(lambda x: None if pd.isnull(x) else replacements.get(x.strip(), x))

    ### type of custody
    replacements = {
        'PRE-CUSTODIAL USE OF FORCE': 'POLICE CUSTODY (PRE-BOOKING)',
        'PRIVATE CORRECTIONAL FACILITY': 'PRIVATE FACILITY',
        'COUNTY JAIL': 'JAIL - COUNTY',
        'MUNICIPAL JAIL': 'JAIL - MUNICIPAL',
        'PENITENTIARY': 'PRISON',
    }
    cdr['type_of_custody'] = cdr['type_of_custody'].apply(lambda x: None if pd.isnull(x) else replacements.get(x.strip(), x))

    ### specific type of custody facility
    replacements = {
    'TDCJ, SPECIFY': 'TDCJ',
    'CUSTODY OF PEACE OFFICER DURING/FLEEING ARREST': 'CUSTODY OF LAW ENFORCEMENT PERSONNEL DURING/FLEEING ARREST',
    'CUSTODY OF PEACE OFFICER SUBSEQUENT TO ARREST': 'CUSTODY OF LAW ENFORCEMENT PERSONNEL AFTER ARREST',
    'CUSTODY OF LAW ENFORCEMENT PERSONNEL SUBSEQUENT TO ARREST': 'CUSTODY OF LAW ENFORCEMENT PERSONNEL AFTER ARREST',
    'TEXAS-JUVENILE JUSTICE DEPARTMENT - FACILITY/DETENTION CENTER, SPECIFY': 'OTHER',
    'TJPC': 'OTHER',
    'TYC': 'OTHER',
    'HALFWAY HOUSE/RESTITUTION CENTER': 'OTHER',
    'CORRECTIONAL/REHABILITATION FACILITY': 'OTHER',
    'NON-LAW ENFORCEMENT DETOX FACILITY': 'OTHER',
}
    cdr['specific_type_of_custody_facility'] = cdr['specific_type_of_custody_facility'].apply(
    lambda x: x if pd.isnull(x) else replacements.get(x.strip(), x))

    ### overwrite "other_behavior" with "specify_other_behavior"
    cdr = fix_other_behavior(cdr)

    ### drop unnecessary/nonsensical columns
    cdr.drop(['entry_date_time_n_a', 'custody_date_na'], axis=1, inplace=True)
    cdr.drop('department_type', axis=1, inplace=True)
    
    ### de-duplicate
    pure_dupes = cdr.duplicated()
    cdr = cdr[~pure_dupes]

    LOGGER.debug("Dropping %d rows that are 100%% duplicates of another row, leaving %d rows" % (pure_dupes.sum(), len(cdr)))

    dedup_rounds = [
        ['cdr_cdr_name'],
        ['first_name', 'last_name', 'date_of_birth'],
        ['first_name', 'last_name', 'death_date'],
    ]
    all_cdrs = [cdr]
    all_merged_records = []
    all_unmerged_frames = []
    all_merge_methods = []
    for i, dr in enumerate(dedup_rounds):
        LOGGER.debug('**** Dedup step %d: find duplicates on these columns:' % (i + 1), dr)
        vals = dedup_cdr_by_col(all_cdrs[-1], dr)
        new_cdr, umf, mr, mm = vals
        all_cdrs.append(new_cdr)
        all_unmerged_frames.append(umf)
        all_merged_records.append(mr)
        all_merge_methods.append(mm)
        dropping = sum(len(f) for f in umf)
        LOGGER.debug("Dropping %d duplicates and adding %d merged records, yielding %d records" % (
            dropping, len(mr), len(new_cdr)))

    LOGGER.debug("Ultimately removing %d duplicate records, leaving %d" % (
        len(all_cdrs[0]) - len(all_cdrs[-1]), len(all_cdrs[-1])))
    cdr = all_cdrs[-1]
    
    for rd, cols in enumerate(dedup_rounds):
        LOGGER.debug("In round %d, there were %d record merges based on" % (rd, len(all_merged_records[rd])), cols)

    ### final cosmetic fixes and add calculated columns
    def get_days(dt):
        if dt.days < -1:
            return None
        elif dt.days == -1:
            return 0
        else:
            return dt.days
    
    def fix_century(df: pd.DataFrame, check_columns: list, compare_column: str) -> pd.DataFrame:
        """
        When converting an ambiguous two-digit year to a four-digit year, Python converts anything below about 75 to use 20** and anything above is still 19**.

        For our purposes, however, this results in very old incident datetimes and dates of birth being converted to the very far future. To remedy this, we'll check the birthdays and incident dates against the date of death. If it is later than the date of death, we'll subject 100 years.

        Adding one day to death datetime to account for deaths that happened on same day as custody.
        """
        years = 100
        days_per_year = 365.24

        for col in check_columns:
            df.reset_index(inplace=True, drop=True)
            LOGGER.debug(f"Checking {col}: {df[df[compare_column] < df[col]].shape}")
            df.loc[df[compare_column] + datetime.timedelta(days=1) < df[col], col] = df[col] - datetime.timedelta(days=(years*days_per_year))

        return df
        
    cdr = fix_century(cdr, ['date_time_of_custody_or_incident'], 'death_date_and_time')
    delta = cdr.death_date_and_time - cdr.date_time_of_custody_or_incident
    LOGGER.debug("For %d records with death date before custoday date, setting the days_from_custody_to_death to NaN" % (delta.dt.days < -1).sum())
    cdr['days_from_custody_to_death'] = delta.apply(get_days)

    cdr['name_full'] = ''
    for col in ['first_name', 'middle_name', 'last_name', 'suffix']:
        cdr['name_full'] = cdr['name_full'] + ' ' + cdr[col].fillna('')
    cdr['name_full'] = cdr['name_full'].apply(lambda s: ' '.join(s.strip().split()))
    cdr.loc[cdr['name_full'] == '', 'name_full'] = np.nan

    cdr['num_revisions'] = cdr['version_number'] - 1
    cdr.drop(['version_type', 'version_number'], axis=1, inplace=True)

    col_renames = {
        'first_name': 'name_first',
        'middle_name': 'name_middle',
        'last_name': 'name_last',
        'suffix': 'name_suffix',
        'cdr_cdr_name': 'record_id',
        'death_causer_other': 'who_caused_death_in_homicide_or_accident_other',
        'who_caused_the_death': 'who_caused_death_in_homicide_or_accident',
        'death_location': 'death_location_type',
        'death_location_elsewhere': 'death_location_type_other',
        'city': 'death_location_city',
        'county': 'death_location_county',
        'street_address': 'death_location_street_address',
        'entry_date_time': 'facility_entry_date_time',
        'pre_existing_medical_condition': 'death_from_pre_existing_medical_condition',
    }

    cdr.rename(columns=col_renames, inplace=True)

    new_order = [
        # Record indexing columns
        'record_id',
        'num_revisions',
        'form_version',
        'report_date',
        'date_time_of_custody_or_incident',

        # Deceased personal information, demographics
        'name_first',
        'name_last',
        'name_middle',
        'name_suffix',
        'name_full',
        'date_of_birth',
        'age_at_time_of_death',
        'sex',
        'race',

        # Death event information
        'death_date',
        'death_date_and_time',
        'death_location_county',
        'death_location_city',
        'death_location_street_address',
        'death_location_type',
        'death_location_type_other',
        'death_from_pre_existing_medical_condition',
        'manner_of_death',
        'manner_of_death_description',
        'means_of_death',
        'means_of_death_other',
        'medical_cause_of_death',
        'medical_examinor_coroner_evalution',
        'medical_treatment',
        'days_from_custody_to_death',
        'who_caused_death_in_homicide_or_accident',
        'who_caused_death_in_homicide_or_accident_other',

        # Criminal information on deceased
        'offense_1',
        'offense_2',
        'offense_3',
        'type_of_offense',
        'type_of_offense_other',
        'were_the_charges',

        # Facility and agency information
        'facility_entry_date_time',
        'type_of_custody',
        'specific_type_of_custody_facility',
        'agency_address',
        'agency_city',
        'agency_county',
        'agency_name',
        'agency_zip',
        
        # Deceased behavior upon entry or custody
        'type_of_restraint',
        'under_restraint',
        'entry_behavior',
        'other_behavior',
        'exhibit_any_medical_problems',
        'exhibit_any_mental_health_problems',
        'make_suicidal_statements',
    ]

    cdr = reorder_columns_and_check(cdr, new_order)

    # TODO: create validation command option to run checks in 5c and other crosstabs
    ### write to s3 - cleaned dataset bucket

    ### TODO: data still has a lot of wonky dates; maybe missed some cleaning?
    save_s3(cdr, 'tji-private-cleaned-datasets', 'cleaned_custodial_death_reports.csv')

    ### TODO: make record of issues still noted in notebook
    # prepare/publish data for website - output to compressed dataset bucket

    ## integrate dataset-specific config from: create_datasets_for_website.ipynb
    ## convert to js/drop columns
    ## bucket age ranges
    ## slider data?
    ## write to compressed s3 bucket

if __name__ == "__main__":
  main()
