# website-data-cleaning
Cleaning data for use on existing website data visualizations

For most of 2025, there has been an issue where new CDR reports (and possibly OIS reports) are not being imported by the existing data cleaning pipeline. This is a temporary solution to get the data flowing to the website again.

Main goals:
- Remove data-dot-world from processing pipeline
- Remove usage of unmaintained Google sheets library in favor of [Google's official API](https://developers.google.com/workspace/sheets/api/quickstart/python)
- Move processing from notebooks to proper scripts

Migration plan:
- Turn off cron job automation in AWS for CDR ONLY by updating the config
- Once this works, port OIS as well
- Disable cron/EC2

Relevant notebooks for CDR:
- [data_cleaning/clean_cdr.ipynb](https://github.com/texas-justice-initiative/data-processing/blob/master/data_cleaning/clean_cdr.ipynb)
- [data_cleaning/create_datasets_for_website.ipynb](https://github.com/texas-justice-initiative/data-processing/blob/master/data_cleaning/create_datasets_for_website.ipynb)
- **Not porting** (because we don't use Tableau anymore): [data_cleaning/transfer_clean_data.ipynb](https://github.com/texas-justice-initiative/data-processing/blob/master/data_cleaning/transfer_clean_data.ipynb)

Google sheets 
    - CDR source: "CDR Reports All:Form Version 2005"
    - The code relies on a client secret of unknown provenance that was being used in the original implementation. We should probably regenerate this at some time but for expediency sake we'll use the legacy one here but move it to secrets manager.

S3 paths:
- Dataset dependencies:
    - reference-data/agencies_and_counties.csv
    - reference-data/reformatted_cdr_2017_master_file.csv
- Intermediate Output: cleaned_custodial_death_reports.csv
- Website data files:
    - all_slider_data.json
    - cdr_compressed.json
    - cdr_compressed_new.json
    - cdr_compressed_new.json.gz
    - cdr_full.csv