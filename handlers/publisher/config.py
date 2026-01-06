INPUT_S3_BUCKET_NAME = "tji-public-cleaned-datasets"
OUTPUT_S3_BUCKET_NAME = "tji-compressed-data"

CONFIG_MAPPING = {"cdr": ["cdr"], "ois": ["ois-civilians", "ois-officers"]}

CONFIGS = {
    "cdr": {
        "FILENAME": "cleaned_custodial_death_reports.csv",
        "OUTFILE_PREFIX": "cdr",
        "DATE_COL": "death_date",
        "ID_COL": "record_id",
        "KEEP_COLS": [
            "record_id",
            "year",
            "race",
            "sex",
            "manner_of_death",
            "age_at_time_of_death",
            "type_of_custody",
            "death_location_type",
            "means_of_death",
            "death_location_county",
            "agency_name",
        ],
    },
    "ois-civilians": {
        "FILENAME": "shot_civilians.csv",
        "OUTFILE_PREFIX": "ois",
        "DATE_COL": "date_incident",
        "ID_COL": None,
        "KEEP_COLS": [
            "year",
            "civilian_race",
            "civilian_gender",
            "civilian_age",
            "civilian_died",
            "officer_age_1",
            "officer_race_1",
            "officer_gender_1",
            "incident_result_of",
            "incident_county",
            "agency_name_1",
            "deadly_weapon",
            "multiple_officers_involved",
        ],
        "RENAMES": {
            "officer_gender_1": "officer_gender",
            "officer_age_1": "officer_age",
            "officer_race_1": "officer_race",
            "agency_name_1": "agency_name",
        },
    },
    "ois-officers": {
        "FILENAME": "shot_officers.csv",
        "OUTFILE_PREFIX": "ois_officers",
        "DATE_COL": "date_incident",
        "ID_COL": None,
        "KEEP_COLS": [
            "year",
            "civilian_race_1",
            "civilian_gender_1",
            "civilian_age_1",
            "civilian_harm",
            "officer_age",
            "officer_race",
            "officer_gender",
            "officer_harm",
            "incident_county",
            "agency_name_1",
        ],
        "RENAMES": {
            "agency_name_1": "agency_name",
        },
    },
}
