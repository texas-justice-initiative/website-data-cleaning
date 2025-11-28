import os.path
from typing import Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from utils.logger import LOGGER

def get_creds(service_account_path: str, scopes: list[str]) -> Optional[service_account.Credentials]:
    if service_account_path is not None and scopes is not None:
        return service_account.Credentials.from_service_account_file(service_account_path, scopes=scopes)
    else:
        raise "Path to service account secret and scopes required"

def retrieve_sheet(config: dict) -> Optional[Tuple[list, list]]:
    credentials: service_account.Credentials = get_creds(config.get('SERVICE_ACCOUNT_FILE'), config.get('SCOPES'))
    
    try:
        service = build("sheets", "v4", credentials=credentials)

        sheet = service.spreadsheets()
        result: dict = (
            sheet.values()
            .get(spreadsheetId=config.get('SPREADSHEET_ID'), range=config.get('RANGE_NAME'))
            .execute()
        )

        values: list[list] = result.get("values", [])
        column_names: list[str] = values[0]
        LOGGER.info({"sheet_name": config.get('RANGE_NAME'), "rows": len(values), "columns": len(column_names)})

        if not values:
            LOGGER.warning("No data found")
            return
        
        return column_names, values[1:]

    except HttpError as err:
        LOGGER.error(err)