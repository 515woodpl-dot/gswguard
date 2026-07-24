import hashlib
from uuid import uuid4

import pytest

from apps.api.app.packages import (
    PackageDownloadService,
    PackageFormat,
    PackageManifest,
    PackageRecord,
    PackageValidationError,
    validate_archive_member,
)


class FakeDrive:
    def __init__(self, chunks: list[bytes]):
        self.chunks = chunks
        self.calls = []

    async def read_chunks(self, file_id, shared_drive_id, chunk_size):
        self.calls.append((file_id, shared_drive_id, chunk_size))
        for chunk in self.chunks:
            yield chunk


class TrustedSignature:
    def verify(self, package_format, package_name, required):
        return True


def package(data=b"installer"):
    return PackageRecord(
        id=uuid4(), organization_id=uuid4(),
        manifest=PackageManifest(package_key="approved.tool", version="1.0.0", format=PackageFormat.msi, publisher="GSW"),
        drive_file_id="drive-file-1", drive_shared_drive_id="shared-drive-1",
        expected_sha256=hashlib.sha256(data).hexdigest(), expected_size_bytes=len(data), approved=True,
    )


async def collect(stream):
    result = bytearray()
    async for chunk in stream:
        result.extend(chunk)
    return bytes(result)


def test_manifest_rejects_shell_arguments_and_unsafe_archive_paths():
    with pytest.raises(ValueError, match="unsafe installer argument"):
        PackageManifest(package_key="tool", version="1", format=PackageFormat.exe, publisher="GSW", executable_name="tool.exe", arguments=["/quiet & whoami"])
    with pytest.raises(PackageValidationError):
        validate_archive_member("../../secret.txt")
    with pytest.raises(PackageValidationError):
        validate_archive_member("C:/Windows/system32/file.dll")


def test_backend_streams_drive_bytes_and_verifies_size_hash_and_signature():
    import asyncio

    data = b"installer-bytes"
    drive = FakeDrive([data[:4], data[4:]])
    service = PackageDownloadService(drive, TrustedSignature())
    assert asyncio.run(collect(service.stream(package(data)))) == data
    assert drive.calls[0][1] == "shared-drive-1"


def test_stream_fails_closed_on_hash_mismatch():
    import asyncio

    item = package(b"expected")
    drive = FakeDrive([b"tampered"])
    with pytest.raises(PackageValidationError, match="hash mismatch"):
        asyncio.run(collect(PackageDownloadService(drive, TrustedSignature()).stream(item)))
