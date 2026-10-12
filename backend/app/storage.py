"""Object storage abstraction.

* ``LocalStorage`` keeps files under ``STORAGE_LOCAL_DIR``. Fine for local
  development and tests; *not* durable on Railway/containers.
* ``S3Storage`` works with any S3-compatible provider (AWS S3, Cloudflare R2,
  Backblaze B2, MinIO). Uploads go straight from the browser to the bucket via
  presigned PUT URLs, so large videos never pass through the API.

Key layout::

    uploads/{store_id}/{video_id}/{safe_filename}   source videos
    artifacts/{job_id}/...                          tracks, snapshots
    frames/{camera_id}/{name}.jpg                   zone-editor reference frames
"""

from __future__ import annotations

import os
import re
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Optional

from app.config import settings

_SAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    base = os.path.basename(name or "video")
    base = _SAFE.sub("_", base).strip("._") or "video"
    return base[:120]


class StorageError(Exception):
    pass


@dataclass
class PresignedUpload:
    method: str
    url: str
    headers: dict
    direct: bool  # True: browser uploads straight to object storage


class LocalStorage:
    name = "local"

    def __init__(self, root: str) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        path = (self.root / key).resolve()
        if self.root not in path.parents and path != self.root:
            raise StorageError("Invalid storage key")
        return path

    def presign_upload(self, key: str, content_type: str, video_id: str) -> PresignedUpload:
        # The API itself receives the bytes (PUT /api/videos/{id}/content).
        return PresignedUpload("PUT", f"/api/videos/{video_id}/content", {"Content-Type": content_type}, False)

    def write_stream(self, key: str, stream: BinaryIO) -> int:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        with open(tmp, "wb") as fh:
            shutil.copyfileobj(stream, fh, length=1024 * 1024)
        os.replace(tmp, path)
        return path.stat().st_size

    def put_file(self, key: str, local_path: str, content_type: Optional[str] = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(local_path, path)

    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> None:
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def get_bytes(self, key: str) -> bytes:
        path = self._path(key)
        if not path.exists():
            raise StorageError(f"Object not found: {key}")
        return path.read_bytes()

    def download_to(self, key: str, local_path: str) -> None:
        path = self._path(key)
        if not path.exists():
            raise StorageError(f"Object not found: {key}")
        shutil.copyfile(path, local_path)

    def size(self, key: str) -> Optional[int]:
        path = self._path(key)
        return path.stat().st_size if path.exists() else None

    def delete(self, key: str) -> None:
        path = self._path(key)
        if path.exists():
            path.unlink()

    def check(self) -> None:
        if not os.access(self.root, os.W_OK):
            raise StorageError(f"Storage directory not writable: {self.root}")


class S3Storage:
    name = "s3"

    def __init__(self) -> None:
        import boto3
        from botocore.config import Config

        if not settings.s3_bucket:
            raise StorageError("S3_BUCKET is not configured")
        self.bucket = settings.s3_bucket
        self.client = boto3.client(
            "s3",
            endpoint_url=settings.s3_endpoint_url or None,
            region_name=settings.s3_region,
            aws_access_key_id=settings.s3_access_key_id,
            aws_secret_access_key=settings.s3_secret_access_key,
            config=Config(signature_version="s3v4", retries={"max_attempts": 5, "mode": "standard"}),
        )

    def presign_upload(self, key: str, content_type: str, video_id: str) -> PresignedUpload:
        url = self.client.generate_presigned_url(
            "put_object",
            Params={"Bucket": self.bucket, "Key": key, "ContentType": content_type},
            ExpiresIn=settings.s3_presign_expiry_seconds,
        )
        return PresignedUpload("PUT", url, {"Content-Type": content_type}, True)

    def write_stream(self, key: str, stream: BinaryIO) -> int:
        self.client.upload_fileobj(stream, self.bucket, key)
        return self.size(key) or 0

    def put_file(self, key: str, local_path: str, content_type: Optional[str] = None) -> None:
        extra = {"ContentType": content_type} if content_type else None
        self.client.upload_file(local_path, self.bucket, key, ExtraArgs=extra)

    def put_bytes(self, key: str, data: bytes, content_type: Optional[str] = None) -> None:
        kwargs = {"ContentType": content_type} if content_type else {}
        self.client.put_object(Bucket=self.bucket, Key=key, Body=data, **kwargs)

    def get_bytes(self, key: str) -> bytes:
        try:
            return self.client.get_object(Bucket=self.bucket, Key=key)["Body"].read()
        except self.client.exceptions.NoSuchKey as exc:
            raise StorageError(f"Object not found: {key}") from exc

    def download_to(self, key: str, local_path: str) -> None:
        self.client.download_file(self.bucket, key, local_path)

    def size(self, key: str) -> Optional[int]:
        from botocore.exceptions import ClientError

        try:
            return int(self.client.head_object(Bucket=self.bucket, Key=key)["ContentLength"])
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return None
            raise

    def delete(self, key: str) -> None:
        self.client.delete_object(Bucket=self.bucket, Key=key)

    def check(self) -> None:
        self.client.head_bucket(Bucket=self.bucket)


_storage = None


def get_storage():
    global _storage
    if _storage is None:
        if settings.storage_backend == "s3":
            _storage = S3Storage()
        else:
            _storage = LocalStorage(settings.storage_local_dir)
    return _storage


def reset_storage() -> None:
    global _storage
    _storage = None
