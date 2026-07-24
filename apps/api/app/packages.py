from __future__ import annotations

import hashlib
import re
from enum import StrEnum
from pathlib import PurePosixPath
from typing import AsyncIterator, Protocol
from uuid import UUID

from pydantic import BaseModel, Field, model_validator


class PackageFormat(StrEnum):
    winget = "winget"
    msi = "msi"
    exe = "exe"
    zip = "zip"


class PackageManifest(BaseModel):
    package_key: str = Field(min_length=1, max_length=160, pattern=r"^[a-zA-Z0-9._-]+$")
    version: str = Field(min_length=1, max_length=80)
    format: PackageFormat
    publisher: str = Field(min_length=1, max_length=240)
    executable_name: str | None = Field(default=None, max_length=240)
    arguments: list[str] = Field(default_factory=list, max_length=32)
    msi_properties: dict[str, str] = Field(default_factory=dict, max_length=32)
    signature_required: bool = True
    allow_reboot: bool = False

    @model_validator(mode="after")
    def validate_manifest(self) -> "PackageManifest":
        if self.format in {PackageFormat.exe, PackageFormat.zip} and not self.executable_name:
            raise ValueError("EXE and ZIP packages require an executable name")
        if self.format == PackageFormat.msi and (self.arguments or self.executable_name):
            raise ValueError("MSI packages use typed properties, not executable arguments")
        if self.format == PackageFormat.winget and (self.arguments or self.msi_properties):
            raise ValueError("Winget packages use pinned catalog metadata, not arbitrary arguments")
        if any(_unsafe_argument(argument) for argument in self.arguments):
            raise ValueError("unsafe installer argument")
        if any(not re.fullmatch(r"[A-Za-z][A-Za-z0-9_.-]{0,63}", key) for key in self.msi_properties):
            raise ValueError("invalid MSI property name")
        return self


def _unsafe_argument(argument: str) -> bool:
    return any(character in argument for character in ("&", "|", ";", "`", "$", "\r", "\n"))


class PackageRecord(BaseModel):
    id: UUID
    organization_id: UUID
    manifest: PackageManifest
    drive_file_id: str | None = None
    drive_shared_drive_id: str | None = None
    expected_sha256: str = Field(pattern=r"^[0-9a-fA-F]{64}$")
    expected_size_bytes: int | None = Field(default=None, ge=0)
    approved: bool = False


class DriveObject(Protocol):
    async def read_chunks(self, file_id: str, shared_drive_id: str | None, chunk_size: int) -> AsyncIterator[bytes]: ...


class SignatureVerifier(Protocol):
    def verify(self, package_format: PackageFormat, package_name: str, required: bool) -> bool: ...


class PackageValidationError(Exception):
    pass


def validate_archive_member(name: str) -> None:
    path = PurePosixPath(name.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or ":" in path.parts[0] if path.parts else False:
        raise PackageValidationError("unsafe archive path")
    if any(part in {"", "."} for part in path.parts):
        raise PackageValidationError("ambiguous archive path")


def validate_package_manifest(package: PackageRecord) -> None:
    if not package.approved:
        raise PackageValidationError("package is not approved")
    if package.manifest.signature_required and package.manifest.format == PackageFormat.winget:
        # Winget is verified by its pinned source/package policy, not local Authenticode here.
        return


class PackageDownloadService:
    def __init__(self, drive: DriveObject, signature_verifier: SignatureVerifier | None = None, max_size_bytes: int = 1_073_741_824):
        self.drive = drive
        self.signature_verifier = signature_verifier
        self.max_size_bytes = max_size_bytes

    async def stream(self, package: PackageRecord, chunk_size: int = 1024 * 1024) -> AsyncIterator[bytes]:
        validate_package_manifest(package)
        if package.drive_file_id is None:
            raise PackageValidationError("package has no Drive file")
        if package.manifest.signature_required and package.manifest.format != PackageFormat.winget:
            if self.signature_verifier is None or not self.signature_verifier.verify(package.manifest.format, package.manifest.package_key, True):
                raise PackageValidationError("package signature is not trusted")
        digest = hashlib.sha256()
        total = 0
        async for chunk in self.drive.read_chunks(package.drive_file_id, package.drive_shared_drive_id, chunk_size):
            total += len(chunk)
            if total > self.max_size_bytes or (package.expected_size_bytes is not None and total > package.expected_size_bytes):
                raise PackageValidationError("package exceeds allowed size")
            digest.update(chunk)
            yield chunk
        if package.expected_size_bytes is not None and total != package.expected_size_bytes:
            raise PackageValidationError("package size mismatch")
        if digest.hexdigest().casefold() != package.expected_sha256.casefold():
            raise PackageValidationError("package hash mismatch")
