import pandas as pd

from utils.logger import LOGGER

def convert_df(header: list[str], rows: list[list]) -> pd.DataFrame:
    return pd.DataFrame(rows, columns=header)

# load agency/county (auxilliary data) from S3