"""Private object storage behind one interface. Local disk for development, any S3-compatible
store (AWS S3, MinIO, R2) for deployment. Files are never public; clients get short-lived signed URLs."""
import time
from abc import ABC, abstractmethod
from pathlib import Path
from urllib.parse import quote, urlencode

from app.core.config import settings
from app.core.errors import AppError
from app.core.security import sign_file_key


class Storage(ABC):
    @abstractmethod
    def put(self, key: str, data: bytes, content_type: str) -> None: ...

    @abstractmethod
    def get(self, key: str) -> bytes: ...

    @abstractmethod
    def signed_url(self, key: str, ttl: int | None = None, download_name: str | None = None) -> str: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...


class LocalStorage(Storage):
    def __init__(self, base_dir: str):
        self.base = Path(base_dir).resolve()
        self.base.mkdir(parents=True, exist_ok=True)

    def path_for(self, key: str) -> Path:
        path = (self.base / key).resolve()
        if self.base not in path.parents:
            raise AppError("invalid_key", "Invalid file key.", 400)
        return path

    def put(self, key, data, content_type):
        path = self.path_for(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get(self, key):
        path = self.path_for(key)
        if not path.exists():
            raise AppError("file_missing", "The stored file is missing.", 404)
        return path.read_bytes()

    def signed_url(self, key, ttl=None, download_name=None):
        exp = int(time.time()) + (ttl or settings.signed_url_ttl_seconds)
        params = {"exp": exp, "sig": sign_file_key(key, exp)}
        if download_name:
            params["name"] = download_name
        return f"{settings.public_api_url}/files/{quote(key)}?{urlencode(params)}"

    def delete(self, key):
        path = self.path_for(key)
        if path.exists():
            path.unlink()


class S3Storage(Storage):
    def __init__(self):
        import boto3

        self.bucket = settings.s3_bucket
        def make(endpoint):
            return boto3.client(
                "s3", endpoint_url=endpoint, region_name=settings.s3_region,
                aws_access_key_id=settings.s3_access_key, aws_secret_access_key=settings.s3_secret_key,
            )

        self.client = make(settings.s3_endpoint_url)
        # Presigned URLs are opened by the browser, which may need a different host than the API
        # uses internally (e.g. http://minio:9000 inside Docker vs http://localhost:9000 outside).
        self.url_client = make(settings.s3_public_endpoint_url) if settings.s3_public_endpoint_url else self.client

    def put(self, key, data, content_type):
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type,
                               ServerSideEncryption="AES256") if not settings.s3_endpoint_url else \
            self.client.put_object(Bucket=self.bucket, Key=key, Body=data, ContentType=content_type)

    def get(self, key):
        return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()

    def signed_url(self, key, ttl=None, download_name=None):
        params = {"Bucket": self.bucket, "Key": key}
        if download_name:
            params["ResponseContentDisposition"] = f'attachment; filename="{download_name}"'
        return self.url_client.generate_presigned_url("get_object", Params=params,
                                                      ExpiresIn=ttl or settings.signed_url_ttl_seconds)

    def delete(self, key):
        self.client.delete_object(Bucket=self.bucket, Key=key)


_storage: Storage | None = None


def get_storage() -> Storage:
    global _storage
    if _storage is None:
        _storage = S3Storage() if settings.storage_backend == "s3" else LocalStorage(settings.local_storage_dir)
    return _storage
