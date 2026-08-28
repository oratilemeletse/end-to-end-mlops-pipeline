"""Tests for deterministic dataset acquisition helpers."""

import hashlib
import zipfile
from pathlib import Path

import pytest

from scripts.download_bank_marketing import (
    extract_member,
    inspect_csv,
    sha256,
    verify_checksum,
)


def test_sha256_returns_expected_digest(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"bank-marketing")

    assert sha256(artifact) == hashlib.sha256(b"bank-marketing").hexdigest()


def test_verify_checksum_rejects_changed_content(tmp_path: Path) -> None:
    artifact = tmp_path / "artifact.bin"
    artifact.write_bytes(b"unexpected")

    with pytest.raises(ValueError, match="Checksum mismatch"):
        verify_checksum(artifact, "0" * 64)


def test_extract_member_extracts_only_requested_file(tmp_path: Path) -> None:
    archive_path = tmp_path / "data.zip"
    destination = tmp_path / "selected.csv"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("selected.csv", "target\n1\n")
        archive.writestr("ignored.csv", "target\n0\n")

    extract_member(archive_path, "selected.csv", destination)

    assert destination.read_text(encoding="utf-8") == "target\n1\n"
    assert not (tmp_path / "ignored.csv").exists()


def test_inspect_csv_counts_semicolon_delimited_shape(tmp_path: Path) -> None:
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("feature;target\n1;yes\n2;no\n", encoding="utf-8")

    assert inspect_csv(csv_path) == (2, 2)
