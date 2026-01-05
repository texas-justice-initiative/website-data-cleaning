from collections import defaultdict
import json

import boto3
from botocore.exceptions import ClientError


def get_secret(scopes: list[str] = []) -> dict:
    secret_name = "data-processing"
    region_name = "us-east-2"

    session = boto3.session.Session(profile_name="tji")
    client = session.client(service_name="secretsmanager", region_name=region_name)

    try:
        get_secret_value_response = client.get_secret_value(SecretId=secret_name)
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e

    secret = json.loads(get_secret_value_response["SecretString"])

    parsed = defaultdict(dict)

    for key, value in secret.items():
        scope, label = key.split(".")
        if scope in scopes:
            parsed[scope].update({label: value})

    return parsed
