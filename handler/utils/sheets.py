import json
from typing import Optional, Tuple

from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from google.oauth2 import service_account

from utils.logger import LOGGER


def get_creds(
    service_account_dict: dict, scopes: list[str]
) -> Optional[service_account.Credentials]:
    if service_account_dict is not None and scopes is not None:
        return service_account.Credentials.from_service_account_info(
            info=service_account_dict, scopes=scopes
        )
    else:
        raise "Service account credential info and scopes required"


def retrieve_sheet(
    client_config: dict, doc_config: dict
) -> Optional[Tuple[list, list]]:
    credentials: service_account.Credentials = get_creds(
        json.loads(client_config.get("client_secret")),
        json.loads(client_config.get("client_scopes")),
    )

    try:
        service = build("sheets", "v4", credentials=credentials)

        sheet = service.spreadsheets()
        result: dict = (
            sheet.values()
            .get(
                spreadsheetId=doc_config.get("spreadsheet_id"),
                range=doc_config.get("range_name"),
            )
            .execute()
        )

        values: list[list] = result.get("values", [])
        column_names: list[str] = values[0]
        LOGGER.info(
            {
                "sheet_name": doc_config.get("range_name"),
                "rows": len(values),
                "columns": len(column_names),
            }
        )

        if not values:
            LOGGER.warning("No data found")
            return

        return column_names, values[1:]

    except HttpError as err:
        LOGGER.error(err)
        return None
