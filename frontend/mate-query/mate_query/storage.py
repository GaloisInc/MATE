"""This module contains helpers for interacting with MATE's object storage service."""

import logging

from minio import Minio
from minio.error import BucketAlreadyExists, BucketAlreadyOwnedByYou

from mate_query.config import MATE_STORAGE_ACCESS_KEY, MATE_STORAGE_SECRET_KEY

logger = logging.getLogger(__name__)

_connection_string = None
client: Minio = None


def initialize(connection_string: str) -> None:
    global client, _connection_string

    if client is not None:
        logger.error(
            f"MATE has already had its storage service initialized with {_connection_string}; skipping"
        )
        return

    _connection_string = connection_string
    client = Minio(
        connection_string,
        access_key=MATE_STORAGE_ACCESS_KEY,
        secret_key=MATE_STORAGE_SECRET_KEY,
        secure=False,
    )

    try:
        client.make_bucket("artifacts")
    except (BucketAlreadyOwnedByYou, BucketAlreadyExists):
        pass
