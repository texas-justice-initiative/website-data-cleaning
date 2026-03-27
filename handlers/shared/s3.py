import json
from tempfile import NamedTemporaryFile, TemporaryDirectory
from zipfile import ZipFile
import boto3

import pandas as pd

from shared.logger import LOGGER


def get_s3_client():
    region_name = "us-east-1"

    session = boto3.session.Session(
        profile_name="tji"
    )  # FIXME: replace with creds dict
    client = session.client(service_name="s3", region_name=region_name)

    return client


def get_s3_data(bucket: str, object_chute: str) -> pd.DataFrame:
    client = get_s3_client()

    with NamedTemporaryFile() as data_file:
        client.download_file(bucket, object_chute, data_file.name)
        data = pd.read_csv(data_file.name)

    return data


def get_s3_json(bucket: str, object_chute: str):
    client = get_s3_client()

    with NamedTemporaryFile() as data_file:
        client.download_file(bucket, object_chute, data_file.name)

        with open(data_file.name, "r") as infile:
            data = json.load(infile)

    return data


def save_s3(df: pd.DataFrame, bucket: str, object_name: str):
    client = get_s3_client()

    with NamedTemporaryFile() as data_file:
        df.to_csv(data_file.name, index=False)
        client.upload_file(data_file.name, bucket, object_name)


def save_s3_json(data: dict, bucket: str, object_name: str, zipped: bool = False):
    client = get_s3_client()

    LOGGER.debug(f"loading: {data.keys()} - {bucket} - {object_name}")
    with TemporaryDirectory() as out_dir:
        LOGGER.debug(f"Created temp directory: {out_dir}")
        upload_filename = f"{out_dir}/{object_name}"
        with open(upload_filename, "w") as outfile:
            json.dump(data, outfile)

        if zipped:
            zipped_file = f"{out_dir}/output.json.gz"
            with ZipFile(zipped_file, "w") as zip_dir:
                zip_dir.write(upload_filename, object_name)
            upload_filename = zipped_file
            object_name = f"{object_name}.gz"

        LOGGER.debug(f"loading: {upload_filename} - {bucket} - {object_name}")
        client.upload_file(upload_filename, bucket, object_name)
