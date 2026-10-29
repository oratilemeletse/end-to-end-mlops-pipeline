"""Download, verify, and convert the UCI Online Retail dataset."""

from __future__ import annotations

import argparse
import json
import shutil
import tempfile
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd

from scripts.download_bank_marketing import (
    extract_member,
    sha256,
    verify_checksum,
)

DATASET_URL = "https://archive.ics.uci.edu/static/public/352/online+retail.zip"
DATASET_DOI = "10.24432/C5BW33"
LICENSE = "CC BY 4.0"
ARCHIVE_SHA256 = "f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b"
WORKBOOK_NAME = "Online Retail.xlsx"
WORKBOOK_SHA256 = "43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d"
EXPECTED_ROWS = 541_909
EXPECTED_COLUMNS = [
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
]
DEFAULT_OUTPUT = Path("data/raw/online-retail.csv")


def validate_retail_frame(
    data: pd.DataFrame,
    *,
    expected_rows: int = EXPECTED_ROWS,
) -> None:
    """Validate source shape and exact column order."""
    if len(data) != expected_rows:
        raise ValueError(
            f"Unexpected retail row count: expected {expected_rows}, received {len(data)}"
        )
    if list(data.columns) != EXPECTED_COLUMNS:
        raise ValueError(
            "Unexpected retail columns: expected "
            f"{EXPECTED_COLUMNS}, received {list(data.columns)}"
        )


def convert_workbook(
    workbook_path: Path,
    output_path: Path,
    *,
    expected_rows: int = EXPECTED_ROWS,
) -> dict[str, Any]:
    """Convert the verified workbook to a deterministic UTF-8 CSV."""
    data = pd.read_excel(workbook_path, engine="openpyxl")
    validate_retail_frame(data, expected_rows=expected_rows)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    data.to_csv(
        output_path,
        index=False,
        date_format="%Y-%m-%d %H:%M:%S",
        lineterminator="\n",
    )
    invoice_dates = pd.to_datetime(data["InvoiceDate"], errors="raise")
    return {
        "rows": len(data),
        "columns": len(data.columns),
        "minimum_invoice_date": invoice_dates.min().isoformat(),
        "maximum_invoice_date": invoice_dates.max().isoformat(),
        "missing_description_rows": int(data["Description"].isna().sum()),
        "missing_customer_id_rows": int(data["CustomerID"].isna().sum()),
        "csv_sha256": sha256(output_path),
    }


def download_dataset(
    output_path: Path = DEFAULT_OUTPUT,
    *,
    archive_path: Path | None = None,
) -> Path:
    """Acquire, verify, convert, and document the Online Retail source."""
    output_path = output_path.resolve()
    metadata_path = output_path.with_suffix(".metadata.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="online-retail-") as temp_dir:
        temp_root = Path(temp_dir)
        archive = temp_root / "online-retail.zip"
        workbook = temp_root / WORKBOOK_NAME
        generated_csv = temp_root / output_path.name
        if archive_path is None:
            urllib.request.urlretrieve(DATASET_URL, archive)
        else:
            if not archive_path.exists():
                raise FileNotFoundError(
                    f"Retail archive does not exist: {archive_path}"
                )
            shutil.copy2(archive_path, archive)
        verify_checksum(archive, ARCHIVE_SHA256)
        extract_member(archive, WORKBOOK_NAME, workbook)
        verify_checksum(workbook, WORKBOOK_SHA256)
        profile = convert_workbook(workbook, generated_csv)
        shutil.copy2(generated_csv, output_path)

    metadata = {
        "dataset": "UCI Online Retail",
        "doi": DATASET_DOI,
        "license": LICENSE,
        "source_url": DATASET_URL,
        "retrieved_at": datetime.now(UTC).isoformat(),
        "archive_sha256": ARCHIVE_SHA256,
        "workbook_sha256": WORKBOOK_SHA256,
        "file": output_path.name,
        "csv_sha256": profile["csv_sha256"],
        "rows": profile["rows"],
        "columns": profile["columns"],
        "column_names": EXPECTED_COLUMNS,
        "minimum_invoice_date": profile["minimum_invoice_date"],
        "maximum_invoice_date": profile["maximum_invoice_date"],
        "missing_description_rows": profile["missing_description_rows"],
        "missing_customer_id_rows": profile["missing_customer_id_rows"],
        "derived_targets": ["next_30d_spend_gbp"],
        "tasks": ["regression", "clustering"],
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return output_path


def parse_args() -> argparse.Namespace:
    """Parse the Online Retail acquisition command."""
    parser = argparse.ArgumentParser(
        description="Download and verify the UCI Online Retail dataset."
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_OUTPUT,
        help=f"Generated CSV path (default: {DEFAULT_OUTPUT})",
    )
    parser.add_argument(
        "--archive",
        type=Path,
        default=None,
        help="Optional predownloaded official archive for offline/retry use.",
    )
    return parser.parse_args()


def main() -> None:
    """Run retail dataset acquisition."""
    args = parse_args()
    output = download_dataset(args.output, archive_path=args.archive)
    metadata = json.loads(
        output.with_suffix(".metadata.json").read_text(encoding="utf-8")
    )
    print(f"Dataset ready: {output}")
    print(f"CSV SHA-256: {metadata['csv_sha256']}")
    print(f"Shape: {metadata['rows']} rows x {metadata['columns']} columns")


if __name__ == "__main__":
    main()
