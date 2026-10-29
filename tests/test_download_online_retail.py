"""Tests for UCI Online Retail acquisition helpers."""

from pathlib import Path

import pandas as pd
import pytest

from scripts.download_online_retail import (
    EXPECTED_COLUMNS,
    convert_workbook,
    validate_retail_frame,
)


def small_retail_frame() -> pd.DataFrame:
    """Return a source-shaped retail fixture."""
    return pd.DataFrame(
        [
            {
                "InvoiceNo": "100",
                "StockCode": "A",
                "Description": "Item A",
                "Quantity": 2,
                "InvoiceDate": pd.Timestamp("2024-01-01 10:00"),
                "UnitPrice": 5.0,
                "CustomerID": 1,
                "Country": "United Kingdom",
            },
            {
                "InvoiceNo": "101",
                "StockCode": "B",
                "Description": None,
                "Quantity": 1,
                "InvoiceDate": pd.Timestamp("2024-01-02 10:00"),
                "UnitPrice": 10.0,
                "CustomerID": None,
                "Country": "United Kingdom",
            },
        ],
        columns=EXPECTED_COLUMNS,
    )


def test_validate_retail_frame_rejects_changed_schema() -> None:
    data = small_retail_frame().drop(columns=["Country"])

    with pytest.raises(ValueError, match="Unexpected retail columns"):
        validate_retail_frame(data, expected_rows=2)


def test_convert_workbook_writes_deterministic_profile(
    tmp_path: Path,
) -> None:
    workbook = tmp_path / "retail.xlsx"
    output = tmp_path / "retail.csv"
    data = small_retail_frame()
    data.to_excel(workbook, index=False)
    profile = convert_workbook(workbook, output, expected_rows=2)

    assert profile["rows"] == 2
    assert profile["missing_description_rows"] == 1
    assert profile["missing_customer_id_rows"] == 1
    assert output.read_text(encoding="utf-8").splitlines()[0] == ",".join(
        EXPECTED_COLUMNS
    )
