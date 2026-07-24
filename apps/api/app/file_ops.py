from __future__ import annotations

import hashlib
import os
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Iterator
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class FileOperationError(Exception):
    pass


class ApprovedFolderPolicy(BaseModel):
    folder_id: UUID
    root: Path
    allowed_extensions: frozenset[str] = frozenset()
    max_file_size_bytes: int = Field(default=100 * 1024 * 1024, ge=1, le=10 * 1024 * 1024 * 1024)
    allow_upload: bool = True
    allow_download: bool = True
    allow_delete: bool = False
    quarantine_enabled: bool = True


@dataclass(frozen=True)
class FileMetadata:
    file_id: UUID
    relative_path: str
    size_bytes: int
    sha256: str
    status: str = "active"


def _reject_component(component: str) -> None:
    if component in {"", ".", ".."} or ":" in component or "\x00" in component:
        raise FileOperationError("unsafe_path")


def resolve_safe_path(policy: ApprovedFolderPolicy, relative_path: str) -> Path:
    if not relative_path or relative_path.startswith(("/", "\\")):
        raise FileOperationError("unsafe_path")
    normalized = relative_path.replace("\\", "/")
    parts = normalized.split("/")
    for component in parts:
        _reject_component(component)
    root = policy.root.resolve()
    candidate = (root / Path(*parts)).resolve(strict=False)
    try:
        candidate.relative_to(root)
    except ValueError as error:
        raise FileOperationError("unsafe_path") from error
    # Reject symlinks/reparse-like links in every existing component. Windows
    # adapters must additionally reject NTFS junction/reparse points.
    current = root
    for component in parts:
        current = current / component
        if current.is_symlink():
            raise FileOperationError("reparse_point")
    return candidate


def validate_extension(policy: ApprovedFolderPolicy, relative_path: str) -> None:
    if policy.allowed_extensions:
        suffix = Path(relative_path).suffix.casefold()
        if suffix not in {extension.casefold() for extension in policy.allowed_extensions}:
            raise FileOperationError("extension_not_allowed")


class LocalApprovedFolderStore:
    """Safe local provider used for tests and development only."""

    def __init__(self, policy: ApprovedFolderPolicy):
        self.policy = policy
        self.policy.root.mkdir(parents=True, exist_ok=True)
        self.quarantine = self.policy.root / ".quarantine"
        self.quarantine.mkdir(exist_ok=True)

    def upload(self, relative_path: str, chunks: Iterable[bytes]) -> FileMetadata:
        if not self.policy.allow_upload:
            raise FileOperationError("upload_not_allowed")
        validate_extension(self.policy, relative_path)
        destination = resolve_safe_path(self.policy, relative_path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        temporary = destination.with_name(f".{destination.name}.{uuid4().hex}.uploading")
        digest = hashlib.sha256()
        total = 0
        try:
            with temporary.open("xb") as handle:
                for chunk in chunks:
                    total += len(chunk)
                    if total > self.policy.max_file_size_bytes:
                        raise FileOperationError("file_too_large")
                    digest.update(chunk)
                    handle.write(chunk)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
        return FileMetadata(uuid4(), relative_path, total, digest.hexdigest())

    def download(self, relative_path: str, chunk_size: int = 1024 * 1024) -> Iterator[bytes]:
        if not self.policy.allow_download:
            raise FileOperationError("download_not_allowed")
        path = resolve_safe_path(self.policy, relative_path)
        if not path.is_file():
            raise FileOperationError("file_not_found")
        with path.open("rb") as handle:
            while chunk := handle.read(chunk_size):
                yield chunk

    def quarantine_file(self, relative_path: str, reason: str) -> str:
        if not self.policy.allow_delete:
            raise FileOperationError("delete_not_allowed")
        if not self.policy.quarantine_enabled:
            raise FileOperationError("quarantine_required")
        path = resolve_safe_path(self.policy, relative_path)
        if not path.is_file():
            raise FileOperationError("file_not_found")
        target = self.quarantine / f"{uuid4().hex}-{path.name}"
        shutil.move(str(path), str(target))
        return reason
