import os.path
from typing import Optional, Tuple

import pandas as pd

from utils.config import load_config
from utils.data import convert_df
from utils.logger import LOGGER
from utils.sheets import retrieve_sheet

# TODO: figure out how to abort if sheet has not been updated since last run
def main():
    # todo: handle multiple sheet tab ranges to extract data from
    config: dict = load_config('config.yaml') # revise: load secrets from secrets manager and toml?

    # load reference data sets

    # loop to retrieve both sheets needed for CDR
    sheet_data: Optional[Tuple[list, list]] = retrieve_sheet(config)

    if sheet_data is not None:
        header, rows = sheet_data
        df: pd.DataFrame = convert_df(header, rows)
    
    LOGGER.info(df.head())

    # combine data from both ranges into one dataset

    # dataset-specific cleaning - output to clean dataset bucket

    ## for CDR
    ### set death datetime to correct type
    ### drop data before 2005
    ### drop unused columns
    ### rename columns
    ### add reference_data:2017_master_file data
        ### check: master file doesn't have any columns not in current dataset
    ### column type conversions/cleanup
        ### clean floats
        ### upcase string columns
        ### make death_date column
    ### standardize columns/formats
        ### race/ethnicity
        ### agency info
        ### death details (lots of columns here)
        ### gender
        ### were there charges
        ### type of custody
        ### specific type of custody facility
        ### over "other_behavior" with "specify_other_behavior"
        ### drop unnecessary/nonsensical columns
    ### de-duplicate
    ### final cosmetic fixes
    ### write to s3
    ### TODO: need to make record of issues still noted in notebook


    # prepare/publish data for website - output to compressed dataset bucket

    ## integrate dataset-specific config from: create_datasets_for_website.ipynb
    ## convert to js/drop columns
    ## bucket age ranges
    ## slider data?
    ## write to compressed s3 bucket

if __name__ == "__main__":
  main()
