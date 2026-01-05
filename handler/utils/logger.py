import logging
from aws_lambda_powertools import Logger

LOGGER: Logger = Logger(level=logging.DEBUG, service="website-data-cleaning")
