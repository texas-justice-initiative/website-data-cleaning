from typing import Tuple
import pandas as pd

from publisher.config import INPUT_S3_BUCKET_NAME
from shared.logger import LOGGER
from shared.s3 import get_s3_data


def compress_data(config) -> Tuple[dict, dict, dict, pd.DataFrame]:
    LOGGER.debug("... Loading data ...")
    slider_data = {}
    slim = get_s3_data(INPUT_S3_BUCKET_NAME, config.get("FILENAME"))

    LOGGER.debug("... Compressing data ...")
    slim["year"] = pd.to_datetime(slim[config["DATE_COL"]]).dt.year
    slim = slim[config["KEEP_COLS"]]
    slim.columns = [config.get("RENAMES", {}).get(c, c) for c in slim.columns]

    compressed = compress_original(slim, id_col=config["ID_COL"])
    compressed_new = compress_new(slim, id_col=config["ID_COL"])

    LOGGER.debug("... Creating slider ...")
    slider_data = {
        "startingYear": compressed["meta"]["lookups"]["year"][0],
        "totalRecords": compressed["meta"]["num_records"],
    }

    return slider_data, compressed, compressed_new


def compress_original(df, id_col=None):
    js = {
        "meta": {
            "num_columns": len(df.columns),
            "num_records": len(df),
            "lookups": {},
        },
        "records": {},
    }
    if id_col:
        js["meta"]["record_ids"] = {"field_name": id_col, "values": list(df[id_col])}
        df = df.drop(id_col, axis=1)
    for col in df.columns:
        values = sorted(list(set(df[col].dropna())))
        mapping = dict((v, i) for i, v in enumerate(values))
        js["meta"]["lookups"][col] = values
        js["records"][col] = (
            df[col].apply(lambda x: -1 if pd.isnull(x) else mapping[x]).tolist()
        )

    return js


def compress_new(df, id_col=None):
    def get_age_group(age):
        if age == "not given":
            return age
        elif age < 18:
            return "under 18"
        elif age < 30:
            return "18 to 29"
        elif age < 40:
            return "30 to 39"
        elif age < 50:
            return "40 to 49"
        elif age < 60:
            return "50 to 59"
        else:
            return "60 and up"

    js = {"records": {}}
    if id_col:
        df = df.drop(id_col, axis=1)
    for col in df.columns:
        js["records"][col] = df[col].fillna("not given").tolist()
        if col in ("age_at_time_of_death", "civilian_age", "officer_age"):
            js["records"]["age_group"] = (
                df[col].apply(lambda x: get_age_group(x)).tolist()
            )

    return js
