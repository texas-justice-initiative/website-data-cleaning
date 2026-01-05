from pathlib import Path


def load_config(path: Path) -> dict:
    # config values
    SERVICE_ACCOUNT_FILE = ""
    SCOPES = [""]
    SPREADSHEET_ID = ""
    RANGE_NAME = "Form Version 2005"
    return {
        "SERVICE_ACCOUNT_FILE": SERVICE_ACCOUNT_FILE,
        "SCOPES": SCOPES,
        "SPREADSHEET_ID": SPREADSHEET_ID,
        "RANGE_NAME": RANGE_NAME,
    }
