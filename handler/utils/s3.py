from tempfile import NamedTemporaryFile

import boto3
from botocore.exceptions import ClientError

import pandas as pd

from utils.logger import LOGGER

def get_s3_client():
    region_name = "us-east-1"

    session = boto3.session.Session(profile_name='tji') # FIXME: replace with creds dict
    client = session.client(
        service_name='s3',
        region_name=region_name
    )

    return client

def get_s3_data(bucket: str, object_chute: str) -> pd.DataFrame:
    client = get_s3_client()

    with NamedTemporaryFile() as data_file:
        client.download_file(bucket, object_chute, data_file.name)

        data = pd.read_csv(data_file.name)
    
    return data

def save_s3(df: pd.DataFrame, bucket: str, object_name: str):
    client = get_s3_client()

    with NamedTemporaryFile() as data_file:
        df.to_csv(data_file.name, index=False)
        client.upload_file(data_file.name, bucket, object_name)