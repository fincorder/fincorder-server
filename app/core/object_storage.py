from functools import lru_cache
from uuid import uuid4

import boto3
from botocore.config import Config

from app.core.config import settings


class ObjectStorageNotConfigured(RuntimeError):
    pass


def _require_storage_settings() -> tuple[str, str, str, str, str]:
    values = (
        settings.AWS_ENDPOINT_URL_S3,
        settings.AWS_ACCESS_KEY_ID,
        settings.AWS_SECRET_ACCESS_KEY,
        settings.AWS_REGION,
        settings.S3_BUCKET,
    )
    if not all(values):
        raise ObjectStorageNotConfigured("Profile image storage is not configured")
    return values  # type: ignore[return-value]


@lru_cache(maxsize=1)
def _s3_client():
    endpoint, access_key, secret_key, region, _ = _require_storage_settings()
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
        region_name=region,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
    )


def upload_profile_image(user_id: str, content: bytes, content_type: str, extension: str) -> str:
    _, _, _, _, bucket = _require_storage_settings()
    key = f"avatars/{user_id}/{uuid4().hex}.{extension}"
    _s3_client().put_object(
        Bucket=bucket,
        Key=key,
        Body=content,
        ContentType=content_type,
        CacheControl="private, max-age=3600",
    )
    return key


def delete_object(key: str) -> None:
    _, _, _, _, bucket = _require_storage_settings()
    _s3_client().delete_object(Bucket=bucket, Key=key)


def create_download_url(key: str) -> str:
    _, _, _, _, bucket = _require_storage_settings()
    expiry = min(max(settings.S3_AVATAR_URL_EXPIRY_SECONDS, 60), 604800)
    return _s3_client().generate_presigned_url(
        "get_object",
        Params={"Bucket": bucket, "Key": key},
        ExpiresIn=expiry,
    )
