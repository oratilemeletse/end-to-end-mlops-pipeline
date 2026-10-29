"""Prepare time-aware retail customer data for regression and clustering."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from src.prepare_data import sha256

EXPECTED_RETAIL_COLUMNS = {
    "InvoiceNo",
    "StockCode",
    "Description",
    "Quantity",
    "InvoiceDate",
    "UnitPrice",
    "CustomerID",
    "Country",
}
TARGET_COLUMN = "next_30d_spend_gbp"
IDENTIFIER_COLUMNS = ["customer_id", "cutoff_date", "target_window_end"]
REGRESSION_FEATURES = [
    "recency_days",
    "history_span_days",
    "purchase_invoices",
    "purchase_lines",
    "monetary_value_gbp",
    "total_quantity",
    "distinct_products",
    "active_days",
    "average_order_value_gbp",
    "average_line_value_gbp",
    "average_quantity_per_invoice",
]
CLUSTERING_FEATURES = [
    "recency_days",
    "purchase_invoices",
    "monetary_value_gbp",
]


@dataclass(frozen=True)
class RetailPreparationConfig:
    """Validated settings for retail snapshot construction."""

    input_path: Path
    output_dir: Path
    history_days: int
    horizon_days: int
    cutoffs: tuple[pd.Timestamp, ...]
    train_cutoffs: tuple[pd.Timestamp, ...]
    validation_cutoffs: tuple[pd.Timestamp, ...]
    test_cutoffs: tuple[pd.Timestamp, ...]
    clustering_cutoff: pd.Timestamp
    random_state: int


def _parse_dates(values: list[str], field: str) -> tuple[pd.Timestamp, ...]:
    """Parse unique, ordered midnight timestamps from configuration."""
    try:
        parsed = tuple(pd.Timestamp(value).normalize() for value in values)
    except (TypeError, ValueError) as error:
        raise ValueError(f"retail_data.{field} contains an invalid date") from error
    if not parsed:
        raise ValueError(f"retail_data.{field} must not be empty")
    if len(set(parsed)) != len(parsed):
        raise ValueError(f"retail_data.{field} must contain unique dates")
    if tuple(sorted(parsed)) != parsed:
        raise ValueError(f"retail_data.{field} must be chronological")
    return parsed


def load_retail_config(path: Path) -> RetailPreparationConfig:
    """Load and validate the customer-intelligence data configuration."""
    if not path.exists():
        raise FileNotFoundError(f"Configuration file does not exist: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        data = raw["retail_data"]
        config = RetailPreparationConfig(
            input_path=Path(data["input_path"]),
            output_dir=Path(data["output_dir"]),
            history_days=int(data["history_days"]),
            horizon_days=int(data["horizon_days"]),
            cutoffs=_parse_dates(data["cutoffs"], "cutoffs"),
            train_cutoffs=_parse_dates(data["train_cutoffs"], "train_cutoffs"),
            validation_cutoffs=_parse_dates(
                data["validation_cutoffs"],
                "validation_cutoffs",
            ),
            test_cutoffs=_parse_dates(data["test_cutoffs"], "test_cutoffs"),
            clustering_cutoff=pd.Timestamp(data["clustering_cutoff"]).normalize(),
            random_state=int(data["random_state"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid retail data configuration in {path}: {error}"
        ) from error

    if config.history_days <= 0:
        raise ValueError("retail_data.history_days must be greater than zero")
    if config.horizon_days <= 0:
        raise ValueError("retail_data.horizon_days must be greater than zero")
    cutoff_set = set(config.cutoffs)
    split_sets = [
        set(config.train_cutoffs),
        set(config.validation_cutoffs),
        set(config.test_cutoffs),
    ]
    if set.union(*split_sets) != cutoff_set:
        raise ValueError("Temporal split cutoffs must contain every configured cutoff")
    if any(
        split_sets[left] & split_sets[right]
        for left in range(len(split_sets))
        for right in range(left + 1, len(split_sets))
    ):
        raise ValueError("Temporal split cutoffs must not overlap")
    return config


def clean_retail_transactions(
    raw_data: pd.DataFrame,
) -> tuple[pd.DataFrame, dict[str, int]]:
    """Validate and clean eligible identified purchase transactions."""
    if raw_data.empty:
        raise ValueError("Retail data must contain at least one row")
    missing = EXPECTED_RETAIL_COLUMNS.difference(raw_data.columns)
    if missing:
        raise ValueError(
            "Retail data is missing required columns: " + ", ".join(sorted(missing))
        )

    data = raw_data[list(sorted(EXPECTED_RETAIL_COLUMNS))].copy()
    data["InvoiceNo"] = data["InvoiceNo"].astype("string").str.strip()
    data["StockCode"] = data["StockCode"].astype("string").str.strip()
    data["Description"] = data["Description"].astype("string").str.strip()
    data["Country"] = data["Country"].astype("string").str.strip()
    data["InvoiceDate"] = pd.to_datetime(data["InvoiceDate"], errors="coerce")
    data["Quantity"] = pd.to_numeric(data["Quantity"], errors="coerce")
    data["UnitPrice"] = pd.to_numeric(data["UnitPrice"], errors="coerce")
    customer_ids = pd.to_numeric(data["CustomerID"], errors="coerce")

    duplicate_rows = data.duplicated().to_numpy(dtype=bool)
    cancellation_rows = (
        data["InvoiceNo"]
        .str.upper()
        .str.startswith("C", na=False)
        .to_numpy(dtype=bool, na_value=False)
    )
    invalid_date_rows = data["InvoiceDate"].isna().to_numpy(dtype=bool)
    invalid_customer_rows = (customer_ids.isna() | (customer_ids % 1 != 0)).to_numpy(
        dtype=bool
    )
    nonpositive_quantity_rows = (
        data["Quantity"].isna() | (data["Quantity"] <= 0)
    ).to_numpy(dtype=bool)
    nonpositive_price_rows = (
        data["UnitPrice"].isna() | (data["UnitPrice"] <= 0)
    ).to_numpy(dtype=bool)

    eligible = ~(
        duplicate_rows
        | cancellation_rows
        | invalid_date_rows
        | invalid_customer_rows
        | nonpositive_quantity_rows
        | nonpositive_price_rows
    )
    cleaned = data.loc[eligible].copy()
    cleaned["customer_id"] = customer_ids.loc[eligible].astype("int64").astype("string")
    cleaned["purchase_value_gbp"] = cleaned["Quantity"] * cleaned["UnitPrice"]
    cleaned = cleaned.rename(
        columns={
            "InvoiceNo": "invoice_no",
            "StockCode": "stock_code",
            "Description": "description",
            "Quantity": "quantity",
            "InvoiceDate": "invoice_date",
            "UnitPrice": "unit_price_gbp",
            "Country": "country",
        }
    )
    cleaned = cleaned[
        [
            "invoice_no",
            "stock_code",
            "description",
            "quantity",
            "invoice_date",
            "unit_price_gbp",
            "customer_id",
            "country",
            "purchase_value_gbp",
        ]
    ].sort_values(["invoice_date", "invoice_no", "stock_code", "customer_id"])
    cleaned = cleaned.reset_index(drop=True)
    report = {
        "source_rows": int(len(data)),
        "duplicate_rows": int(duplicate_rows.sum()),
        "cancellation_rows": int(cancellation_rows.sum()),
        "invalid_date_rows": int(invalid_date_rows.sum()),
        "invalid_customer_rows": int(invalid_customer_rows.sum()),
        "nonpositive_quantity_rows": int(nonpositive_quantity_rows.sum()),
        "nonpositive_price_rows": int(nonpositive_price_rows.sum()),
        "eligible_rows": int(len(cleaned)),
        "eligible_customers": int(cleaned["customer_id"].nunique()),
    }
    if cleaned.empty:
        raise ValueError("Retail cleaning removed every source row")
    return cleaned, report


def _customer_history_features(
    history: pd.DataFrame,
    cutoff: pd.Timestamp,
) -> pd.DataFrame:
    """Aggregate deterministic customer features from pre-cutoff purchases."""
    grouped = history.groupby("customer_id", sort=True)
    features = grouped.agg(
        first_purchase=("invoice_date", "min"),
        last_purchase=("invoice_date", "max"),
        purchase_invoices=("invoice_no", "nunique"),
        purchase_lines=("invoice_no", "size"),
        monetary_value_gbp=("purchase_value_gbp", "sum"),
        total_quantity=("quantity", "sum"),
        distinct_products=("stock_code", "nunique"),
        active_days=("invoice_date", lambda values: values.dt.normalize().nunique()),
    ).reset_index()
    features["recency_days"] = (
        cutoff - features["last_purchase"]
    ).dt.total_seconds() / 86_400
    features["history_span_days"] = (
        cutoff - features["first_purchase"]
    ).dt.total_seconds() / 86_400
    features["average_order_value_gbp"] = (
        features["monetary_value_gbp"] / features["purchase_invoices"]
    )
    features["average_line_value_gbp"] = (
        features["monetary_value_gbp"] / features["purchase_lines"]
    )
    features["average_quantity_per_invoice"] = (
        features["total_quantity"] / features["purchase_invoices"]
    )
    return features.drop(columns=["first_purchase", "last_purchase"])


def build_customer_snapshot(
    transactions: pd.DataFrame,
    *,
    cutoff: pd.Timestamp,
    history_days: int,
    horizon_days: int,
    include_target: bool,
) -> pd.DataFrame:
    """Build a customer snapshot using only history before its cutoff."""
    cutoff = pd.Timestamp(cutoff).normalize()
    history_start = cutoff - pd.Timedelta(days=history_days)
    target_end = cutoff + pd.Timedelta(days=horizon_days)
    history = transactions.loc[
        (transactions["invoice_date"] >= history_start)
        & (transactions["invoice_date"] < cutoff)
    ]
    if history.empty:
        raise ValueError(f"No customer history exists for cutoff {cutoff.date()}")

    snapshot = _customer_history_features(history, cutoff)
    snapshot.insert(1, "cutoff_date", cutoff.date().isoformat())
    snapshot.insert(2, "target_window_end", target_end.date().isoformat())
    if include_target:
        future = transactions.loc[
            (transactions["invoice_date"] >= cutoff)
            & (transactions["invoice_date"] < target_end)
        ]
        target = future.groupby("customer_id")["purchase_value_gbp"].sum()
        snapshot[TARGET_COLUMN] = (
            snapshot["customer_id"].map(target).fillna(0.0).astype(float)
        )
    snapshot = snapshot[
        IDENTIFIER_COLUMNS
        + REGRESSION_FEATURES
        + ([TARGET_COLUMN] if include_target else [])
    ]
    numeric = snapshot[REGRESSION_FEATURES]
    if not np.isfinite(numeric.to_numpy(dtype=float)).all():
        raise ValueError("Customer snapshot contains non-finite feature values")
    return snapshot.sort_values("customer_id").reset_index(drop=True)


def validate_temporal_coverage(
    transactions: pd.DataFrame,
    config: RetailPreparationConfig,
) -> None:
    """Prove full history/outcome coverage and non-overlapping split windows."""
    minimum_date = transactions["invoice_date"].min()
    maximum_date = transactions["invoice_date"].max()
    first_history_start = min(config.cutoffs) - pd.Timedelta(days=config.history_days)
    final_target_end = max(config.cutoffs) + pd.Timedelta(days=config.horizon_days)
    if first_history_start < minimum_date:
        raise ValueError("The first cutoff does not have a complete history window")
    if final_target_end > maximum_date:
        raise ValueError("The final cutoff does not have a complete outcome window")

    train_end = max(config.train_cutoffs) + pd.Timedelta(days=config.horizon_days)
    validation_start = min(config.validation_cutoffs)
    validation_end = max(config.validation_cutoffs) + pd.Timedelta(
        days=config.horizon_days
    )
    test_start = min(config.test_cutoffs)
    if train_end > validation_start:
        raise ValueError("Training outcomes overlap validation feature cutoffs")
    if validation_end > test_start:
        raise ValueError("Validation outcomes overlap test feature cutoffs")


def _write_frame(frame: pd.DataFrame, path: Path) -> dict[str, Any]:
    """Write a CSV and return deterministic artifact metadata."""
    frame.to_csv(path, index=False)
    result: dict[str, Any] = {
        "path": str(path),
        "sha256": sha256(path),
        "rows": int(len(frame)),
        "columns": int(len(frame.columns)),
    }
    if TARGET_COLUMN in frame:
        result["zero_target_fraction"] = float((frame[TARGET_COLUMN] == 0).mean())
        result["target_sum_gbp"] = float(frame[TARGET_COLUMN].sum())
    return result


def prepare_customer_intelligence_data(
    config_path: Path,
    *,
    input_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Clean transactions and persist leakage-safe customer datasets."""
    config = load_retail_config(config_path)
    source_path = input_path or config.input_path
    destination = output_dir or config.output_dir
    if not source_path.exists():
        raise FileNotFoundError(
            f"Retail dataset does not exist: {source_path}. "
            "Run python -m scripts.download_online_retail first."
        )

    raw_data = pd.read_csv(source_path, low_memory=False)
    transactions, cleaning = clean_retail_transactions(raw_data)
    validate_temporal_coverage(transactions, config)
    snapshots = pd.concat(
        [
            build_customer_snapshot(
                transactions,
                cutoff=cutoff,
                history_days=config.history_days,
                horizon_days=config.horizon_days,
                include_target=True,
            )
            for cutoff in config.cutoffs
        ],
        ignore_index=True,
    )
    cutoff_values = snapshots["cutoff_date"]

    def split(cutoffs: tuple[pd.Timestamp, ...]) -> pd.DataFrame:
        values = {value.date().isoformat() for value in cutoffs}
        return snapshots.loc[cutoff_values.isin(values)].reset_index(drop=True)

    outputs = {
        "train": split(config.train_cutoffs),
        "validation": split(config.validation_cutoffs),
        "test": split(config.test_cutoffs),
        "clustering": build_customer_snapshot(
            transactions,
            cutoff=config.clustering_cutoff,
            history_days=config.history_days,
            horizon_days=config.horizon_days,
            include_target=False,
        ),
    }
    destination.mkdir(parents=True, exist_ok=True)
    artifact_metadata = {
        name: _write_frame(frame, destination / f"{name}.csv")
        for name, frame in outputs.items()
    }
    cleaned_path = destination / "cleaned_transactions.csv"
    artifact_metadata["cleaned_transactions"] = _write_frame(
        transactions,
        cleaned_path,
    )
    metadata: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "task_ids": ["CI-A.1.1", "CI-A.1.2", "CI-A.2.1", "CI-A.2.2"],
        "source": {
            "path": str(source_path),
            "sha256": sha256(source_path),
            "minimum_invoice_date": transactions["invoice_date"].min().isoformat(),
            "maximum_invoice_date": transactions["invoice_date"].max().isoformat(),
        },
        "cleaning": cleaning,
        "configuration": {
            "path": str(config_path),
            "history_days": config.history_days,
            "horizon_days": config.horizon_days,
            "cutoffs": [value.date().isoformat() for value in config.cutoffs],
            "train_cutoffs": [
                value.date().isoformat() for value in config.train_cutoffs
            ],
            "validation_cutoffs": [
                value.date().isoformat() for value in config.validation_cutoffs
            ],
            "test_cutoffs": [value.date().isoformat() for value in config.test_cutoffs],
            "clustering_cutoff": config.clustering_cutoff.date().isoformat(),
            "random_state": config.random_state,
            "target_column": TARGET_COLUMN,
            "regression_features": REGRESSION_FEATURES,
            "clustering_features": CLUSTERING_FEATURES,
        },
        "artifacts": artifact_metadata,
    }
    (destination / "metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def parse_args() -> argparse.Namespace:
    """Parse the retail preparation command."""
    parser = argparse.ArgumentParser(
        description="Prepare customer snapshots for regression and clustering."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/customer_intelligence.json"),
    )
    parser.add_argument("--input-data", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, default=None)
    return parser.parse_args()


def main() -> None:
    """Run the customer-intelligence data preparation stage."""
    args = parse_args()
    metadata = prepare_customer_intelligence_data(
        args.config,
        input_path=args.input_data,
        output_dir=args.output_dir,
    )
    print(
        "Retail preparation complete: "
        f"{metadata['cleaning']['eligible_rows']} eligible transactions, "
        f"{metadata['cleaning']['eligible_customers']} customers"
    )


if __name__ == "__main__":
    main()
