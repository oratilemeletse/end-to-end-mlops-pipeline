"""Tests for time-aware retail customer data preparation."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.customer_intelligence_data import (
    TARGET_COLUMN,
    build_customer_snapshot,
    clean_retail_transactions,
    load_retail_config,
    validate_temporal_coverage,
)


def raw_transactions() -> pd.DataFrame:
    """Return a small retail fixture containing valid and invalid rows."""
    return pd.DataFrame(
        [
            {
                "InvoiceNo": "100",
                "StockCode": "A",
                "Description": "Item A",
                "Quantity": 2,
                "InvoiceDate": "2024-01-10 10:00",
                "UnitPrice": 5.0,
                "CustomerID": 1,
                "Country": "UK",
            },
            {
                "InvoiceNo": "101",
                "StockCode": "B",
                "Description": "Item B",
                "Quantity": 1,
                "InvoiceDate": "2024-01-20 10:00",
                "UnitPrice": 10.0,
                "CustomerID": 1,
                "Country": "UK",
            },
            {
                "InvoiceNo": "102",
                "StockCode": "A",
                "Description": "Item A",
                "Quantity": 3,
                "InvoiceDate": "2024-02-05 10:00",
                "UnitPrice": 5.0,
                "CustomerID": 1,
                "Country": "UK",
            },
            {
                "InvoiceNo": "103",
                "StockCode": "C",
                "Description": "Item C",
                "Quantity": 4,
                "InvoiceDate": "2024-01-25 12:00",
                "UnitPrice": 2.0,
                "CustomerID": 2,
                "Country": "UK",
            },
            {
                "InvoiceNo": "C104",
                "StockCode": "C",
                "Description": "Item C",
                "Quantity": -1,
                "InvoiceDate": "2024-01-26 12:00",
                "UnitPrice": 2.0,
                "CustomerID": 2,
                "Country": "UK",
            },
            {
                "InvoiceNo": "105",
                "StockCode": "D",
                "Description": "Item D",
                "Quantity": 1,
                "InvoiceDate": "2024-01-27 12:00",
                "UnitPrice": 3.0,
                "CustomerID": None,
                "Country": "UK",
            },
        ]
    )


def test_cleaning_excludes_cancellations_and_unidentified_rows() -> None:
    cleaned, report = clean_retail_transactions(raw_transactions())

    assert len(cleaned) == 4
    assert report["cancellation_rows"] == 1
    assert report["invalid_customer_rows"] == 1
    assert report["eligible_customers"] == 2
    assert cleaned["purchase_value_gbp"].sum() == 43.0


def test_snapshot_uses_history_and_includes_known_zero_targets() -> None:
    cleaned, _ = clean_retail_transactions(raw_transactions())

    snapshot = build_customer_snapshot(
        cleaned,
        cutoff=pd.Timestamp("2024-02-01"),
        history_days=31,
        horizon_days=28,
        include_target=True,
    )

    customer_one = snapshot.loc[snapshot["customer_id"] == "1"].iloc[0]
    customer_two = snapshot.loc[snapshot["customer_id"] == "2"].iloc[0]
    assert customer_one["monetary_value_gbp"] == 20.0
    assert customer_one[TARGET_COLUMN] == 15.0
    assert customer_two[TARGET_COLUMN] == 0.0
    assert customer_one["purchase_invoices"] == 2


def test_temporal_coverage_rejects_incomplete_outcome_window(
    tmp_path: Path,
) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "retail_data": {
                    "input_path": "unused.csv",
                    "output_dir": "unused",
                    "history_days": 10,
                    "horizon_days": 30,
                    "cutoffs": ["2024-02-01", "2024-03-01", "2024-04-01"],
                    "train_cutoffs": ["2024-02-01"],
                    "validation_cutoffs": ["2024-03-01"],
                    "test_cutoffs": ["2024-04-01"],
                    "clustering_cutoff": "2024-04-01",
                    "random_state": 42,
                }
            }
        ),
        encoding="utf-8",
    )
    config = load_retail_config(config_path)
    cleaned, _ = clean_retail_transactions(raw_transactions())

    with pytest.raises(ValueError, match="complete outcome window"):
        validate_temporal_coverage(cleaned, config)


def test_config_rejects_split_overlap(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "retail_data": {
                    "input_path": "unused.csv",
                    "output_dir": "unused",
                    "history_days": 30,
                    "horizon_days": 30,
                    "cutoffs": ["2024-02-01", "2024-03-01"],
                    "train_cutoffs": ["2024-02-01"],
                    "validation_cutoffs": ["2024-02-01"],
                    "test_cutoffs": ["2024-03-01"],
                    "clustering_cutoff": "2024-03-01",
                    "random_state": 42,
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="must not overlap"):
        load_retail_config(config_path)
