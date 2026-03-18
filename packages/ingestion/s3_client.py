"""
S3 Client.

Manages file storage for Verus document ingestion.

In production: AWS S3, using boto3.
In development/testing: local filesystem, using the path configured
by VERUS_LOCAL_STORAGE_PATH (default: /tmp/verus_dev_storage).

The dev mode switch is controlled by the VERUS_STORAGE_BACKEND
environment variable:
  "s3"    — real AWS S3 (requires AWS credentials)
  "local" — local filesystem (default in dev/test)

Key structure (same regardless of backend):
  {engagement_id}/raw/{document_id}/{filename}          ← uploaded file
  {engagement_id}/normalized/{document_id}/output.json  ← normalised output
  {engagement_id}/deliverables/{filename}               ← rendered reports

Security note on S3 keys:
  The engagement_id prefix ensures that per-engagement IAM policies
  can restrict access to exactly one engagement's objects.
  The application never constructs a key that crosses engagement boundaries.
"""
from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path
from typing import BinaryIO, Optional, Union

logger = logging.getLogger(__name__)

_BACKEND = os.environ.get("VERUS_STORAGE_BACKEND", "local")
_LOCAL_ROOT = Path(
    os.environ.get("VERUS_LOCAL_STORAGE_PATH", "/tmp/verus_dev_storage")
)
_S3_BUCKET = os.environ.get("VERUS_S3_BUCKET", "verus-diligence")


class StorageError(Exception):
    """Raised when a storage operation fails."""


class S3Client:
    """
    File storage client.

    Transparently switches between S3 (production) and local filesystem
    (development/testing) based on VERUS_STORAGE_BACKEND.

    All methods raise StorageError on failure — callers never receive
    raw boto3 or OS exceptions.
    """

    def __init__(
        self,
        backend: Optional[str] = None,
        local_root: Optional[Path] = None,
        bucket: Optional[str] = None,
    ) -> None:
        self._backend  = backend or _BACKEND
        self._root     = local_root or _LOCAL_ROOT
        self._bucket   = bucket or _S3_BUCKET
        self._s3       = None   # lazy init for boto3

    # ── Upload ─────────────────────────────────────────────────────────────────

    def upload_file(
        self,
        file_path: Union[str, Path],
        s3_key: str,
    ) -> str:
        """
        Upload a file from the local filesystem to storage.

        Args:
            file_path: Local path to the file to upload.
            s3_key:    The destination key (path within the bucket/root).

        Returns:
            The s3_key (for recording in the DB).

        Raises:
            StorageError on any failure.
        """
        if self._backend == "local":
            return self._local_upload(Path(file_path), s3_key)
        return self._s3_upload(Path(file_path), s3_key)

    def upload_bytes(
        self,
        data: bytes,
        s3_key: str,
        content_type: str = "application/octet-stream",
    ) -> str:
        """
        Upload raw bytes to storage.

        Returns:
            The s3_key.
        """
        if self._backend == "local":
            return self._local_upload_bytes(data, s3_key)
        return self._s3_upload_bytes(data, s3_key, content_type)

    # ── Download ───────────────────────────────────────────────────────────────

    def download_bytes(self, s3_key: str) -> bytes:
        """
        Download a file from storage and return its contents as bytes.

        Raises:
            StorageError if the key does not exist or download fails.
        """
        if self._backend == "local":
            return self._local_download_bytes(s3_key)
        return self._s3_download_bytes(s3_key)

    def download_to_file(
        self,
        s3_key: str,
        local_path: Union[str, Path],
    ) -> Path:
        """
        Download a file from storage to a local path.

        Returns:
            The local_path (as a Path object).
        """
        data = self.download_bytes(s3_key)
        dest = Path(local_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return dest

    # ── Exists / Delete ────────────────────────────────────────────────────────

    def exists(self, s3_key: str) -> bool:
        """Return True if the key exists in storage."""
        if self._backend == "local":
            return (self._root / s3_key).exists()
        try:
            self._get_s3().head_object(Bucket=self._bucket, Key=s3_key)
            return True
        except Exception:
            return False

    def delete(self, s3_key: str) -> bool:
        """
        Delete an object from storage.
        Returns True if deleted, False if it did not exist.
        """
        if self._backend == "local":
            path = self._root / s3_key
            if path.exists():
                path.unlink()
                return True
            return False
        try:
            self._get_s3().delete_object(Bucket=self._bucket, Key=s3_key)
            return True
        except Exception:
            return False

    def get_presigned_url(
        self,
        s3_key: str,
        expiry_seconds: int = 3600,
    ) -> str:
        """
        Generate a presigned URL for temporary download access.
        In dev mode, returns a local file:// URL.
        """
        if self._backend == "local":
            path = self._root / s3_key
            return f"file://{path}"
        try:
            return self._get_s3().generate_presigned_url(
                "get_object",
                Params={"Bucket": self._bucket, "Key": s3_key},
                ExpiresIn=expiry_seconds,
            )
        except Exception as exc:
            raise StorageError(f"Failed to generate presigned URL: {exc}") from exc

    # ── Local backend ──────────────────────────────────────────────────────────

    def _local_upload(self, src: Path, key: str) -> str:
        try:
            dest = self._root / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
            logger.debug("Local upload: %s → %s", src, dest)
            return key
        except Exception as exc:
            raise StorageError(f"Local upload failed: {exc}") from exc

    def _local_upload_bytes(self, data: bytes, key: str) -> str:
        try:
            dest = self._root / key
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return key
        except Exception as exc:
            raise StorageError(f"Local upload_bytes failed: {exc}") from exc

    def _local_download_bytes(self, key: str) -> bytes:
        path = self._root / key
        if not path.exists():
            raise StorageError(
                f"Key '{key}' not found in local storage at {path}"
            )
        try:
            return path.read_bytes()
        except Exception as exc:
            raise StorageError(f"Local download failed: {exc}") from exc

    # ── S3 backend ─────────────────────────────────────────────────────────────

    def _get_s3(self):
        if self._s3 is None:
            try:
                import boto3
                self._s3 = boto3.client("s3")
            except ImportError as exc:
                raise StorageError(
                    "boto3 is required for S3 storage. "
                    "Install it: pip install boto3"
                ) from exc
        return self._s3

    def _s3_upload(self, src: Path, key: str) -> str:
        try:
            self._get_s3().upload_file(str(src), self._bucket, key)
            logger.debug("S3 upload: %s → s3://%s/%s", src, self._bucket, key)
            return key
        except Exception as exc:
            raise StorageError(f"S3 upload failed: {exc}") from exc

    def _s3_upload_bytes(
        self,
        data: bytes,
        key: str,
        content_type: str,
    ) -> str:
        try:
            import io
            self._get_s3().upload_fileobj(
                io.BytesIO(data),
                self._bucket,
                key,
                ExtraArgs={"ContentType": content_type},
            )
            return key
        except Exception as exc:
            raise StorageError(f"S3 upload_bytes failed: {exc}") from exc

    def _s3_download_bytes(self, key: str) -> bytes:
        try:
            import io
            buf = io.BytesIO()
            self._get_s3().download_fileobj(self._bucket, key, buf)
            return buf.getvalue()
        except Exception as exc:
            raise StorageError(f"S3 download failed for key '{key}': {exc}") from exc
