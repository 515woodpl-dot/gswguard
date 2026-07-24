from pathlib import Path
from uuid import uuid4

import pytest

from apps.api.app.file_ops import (
    ApprovedFolderPolicy,
    FileOperationError,
    LocalApprovedFolderStore,
    resolve_safe_path,
)


def store(tmp_path: Path) -> LocalApprovedFolderStore:
    return LocalApprovedFolderStore(
        ApprovedFolderPolicy(folder_id=uuid4(), root=tmp_path / "company", allowed_extensions=frozenset({".txt"}), max_file_size_bytes=16, allow_delete=True)
    )


def test_upload_download_and_quarantine_are_bounded(tmp_path: Path):
    provider = store(tmp_path)
    metadata = provider.upload("reports/today.txt", [b"hello", b" world"])
    assert metadata.size_bytes == 11
    assert b"".join(provider.download("reports/today.txt")) == b"hello world"
    provider.quarantine_file("reports/today.txt", "owner requested cleanup")
    assert not (tmp_path / "company/reports/today.txt").exists()


def test_path_traversal_reparse_and_policy_abuse_are_rejected(tmp_path: Path):
    provider = store(tmp_path)
    with pytest.raises(FileOperationError, match="unsafe_path"):
        resolve_safe_path(provider.policy, "../secret.txt")
    with pytest.raises(FileOperationError, match="extension_not_allowed"):
        provider.upload("reports/secret.exe", [b"bad"])
    with pytest.raises(FileOperationError, match="file_too_large"):
        provider.upload("reports/big.txt", [b"01234567890123456"])
    link = provider.policy.root / "link"
    link.symlink_to(tmp_path)
    with pytest.raises(FileOperationError, match="unsafe_path|reparse_point"):
        resolve_safe_path(provider.policy, "link/escape.txt")
