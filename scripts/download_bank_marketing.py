"""Download and verify the UCI Bank Marketing dataset."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import tempfile
import urllib.request
import zipfile
from datetime import UTC, datetime
from pathlib import Path

DATASET_URL = "https://archive.ics.uci.edu/static/public/222/bank+marketing.zip"
DATASET_DOI = "10.24432/C5K306"
OUTER_ARCHIVE_SHA256 = (
    "e0bf5f5de5b846e2f18e9d90606637267d46dfa260e0f17bb12e605db5efbeb4"
)
NESTED_ARCHIVE_NAME = "bank-additional.zip"
NESTED_ARCHIVE_SHA256 = (
    "a607b5edab6c6c75ce09c39142a77702c38123bd5aa7ae89a63503bbe17d65cd"
)
CSV_ARCHIVE_NAME = "bank-additional/bank-additional-full.csv"
CSV_SHA256 = "74adfc578bf77a7ff4bb1ba4a9f8709d9e3c6907342959c2c8416847e0afb4d8"
EXPECTED_ROWS = 41_188
EXPECTED_COLUMNS = 21
DEFAULT_OUTPUT = Path("data/raw/bank-additional-full.csv")


def sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify_checksum(path: Path, expected: str) -> None:
    """Raise an error when a file does not match its expected checksum."""
    actual = sha256(path)
    if actual != expected:
        raise ValueError(
            f"Checksum mismatch for {path.name}: expected {expected}, received {actual}"
        )


def inspect_csv(path: Path) -> tuple[int, int]:
    """Return data row and column counts after validating the CSV shape."""
    with path.open("r", encoding="utf-8", newline="") as file_handle:
        reader = csv.reader(file_handle, delimiter=";")
        header = next(reader)
        row_count = sum(1 for _ in reader)
    return row_count, len(header)


def extract_member(
    archive_path: Path,
    member_name: str,
    destination: Path,
) -> None:
    """Extract one known archive member without accepting arbitrary paths."""
    with zipfile.ZipFile(archive_path) as archive:
        try:
            member = archive.getinfo(member_name)
        except KeyError as error:
            raise FileNotFoundError(
                f"{member_name} is missing from {archive_path.name}"
            ) from error

        destination.parent.mkdir(parents=True, exist_ok=True)
        with archive.open(member) as source, destination.open("wb") as target:
            shutil.copyfileobj(source, target)


def download_dataset(output_path: Path = DEFAULT_OUTPUT) -> Path:
    """Download, verify, and extract the selected dataset CSV."""
    output_path = output_path.resolve()
    metadata_path = output_path.with_suffix(".metadata.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="bank-marketing-") as temp_dir:
        temp_root = Path(temp_dir)
        outer_archive = temp_root / "bank-marketing.zip"
        nested_archive = temp_root / NESTED_ARCHIVE_NAME
        extracted_csv = temp_root / output_path.name

        urllib.request.urlretrieve(DATASET_URL, outer_archive)
        verify_checksum(outer_archive, OUTER_ARCHIVE_SHA256)

        extract_member(
            outer_archive,
            NESTED_ARCHIVE_NAME,
            nested_archive,
        )
        verify_checksum(nested_archive, NESTED_ARCHIVE_SHA256)

        extract_member(
            nested_archive,
            CSV_ARCHIVE_NAME,
            extracted_csv,
        )
        verify_checksum(extracted_csv, CSV_SHA256)

        row_count, column_count = inspect_csv(extracted_csv)
        if (row_count, column_count) != (
            EXPECTED_ROWS,
            EXPECTED_COLUMNS,
        ):
            raise ValueError(
                "Unexpected dataset shape: expected "
                f"{EXPECTED_ROWS} rows and {EXPECTED_COLUMNS} columns, "
                f"received {row_count} rows and {column_count} columns"
            )

        shutil.copy2(extracted_csv, output_path)

    metadata = {
        "dataset": "UCI Bank Marketing",
        "doi": DATASET_DOI,
        "source_url": DATASET_URL,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "file": output_path.name,
        "sha256": CSV_SHA256,
        "rows": EXPECTED_ROWS,
        "columns": EXPECTED_COLUMNS,
        "delimiter": ";",
        "target": "y",
        "excluded_features": ["duration"],
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Download and verify the UCI Bank Marketing dataset."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"CSV output path (default: {DEFAULT_OUTPUT})",
    )
    return parser.parse_args()


def main() -> None:
    """Run the dataset download command."""
    args = parse_args()
    output_path = download_dataset(args.output)
    print(f"Dataset ready: {output_path}")
    print(f"SHA-256: {CSV_SHA256}")
    print(f"Shape: {EXPECTED_ROWS} rows x {EXPECTED_COLUMNS} columns")


if __name__ == "__main__":
    main()
