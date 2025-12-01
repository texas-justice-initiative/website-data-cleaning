import pandas as pd

from utils.logger import LOGGER

def convert_df(header: list[str], rows: list[list]) -> pd.DataFrame:
    """
    Correct any length mismatches between data and header row, then combine into single dataframe
    """
    df: pd.DataFrame = pd.DataFrame(rows)
    col_diff: int = len(df.columns) - len(header)

    if col_diff > 0:
        header.extend([f'UNK_{idx}' for idx in range(0,col_diff)])
    elif col_diff < 0:
        for idx in range(0, -1 * col_diff):
            df[f"UNK_{idx}"] = ''
    df.columns = header
    return df

# load agency/county (auxilliary data) from S3