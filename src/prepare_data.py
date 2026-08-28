"""Validate and split the Bank Marketing dataset reproducibly."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.model_selection import train_test_split

EXPECTED_COLUMNS = {
    "age",
    "job",
    "marital",
    "education",
    "default",
    "housing",
    "loan",
    "contact",
    "month",
    "day_of_week",
    "duration",
    "campaign",
    "pdays",
    "previous",
    "poutcome",
    "emp.var.rate",
    "cons.price.idx",
    "cons.conf.idx",
    "euribor3m",
    "nr.employed",
    "y",
}
EXPECTED_TARGET_VALUES = {"no", "yes"}


@dataclass(frozen=True)
class PreparationConfig:
    """Validated settings for the data preparation stage."""

    input_path: Path
    output_dir: Path
    target_column: str
    excluded_features: tuple[str, ...]
    test_size: float
    random_state: int


def sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_config(path: Path) -> PreparationConfig:
    """Load and validate preparation settings from a JSON configuration."""
    if not path.exists():
        raise FileNotFoundError(f"Configuration file does not exist: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        data = raw["data"]
        config = PreparationConfig(
            input_path=Path(data["input_path"]),
            output_dir=Path(data["output_dir"]),
            target_column=str(data["target_column"]),
            excluded_features=tuple(data["excluded_features"]),
            test_size=float(data["test_size"]),
            random_state=int(data["random_state"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid data preparation configuration in {path}: {error}"
        ) from error

    if not 0 < config.test_size < 1:
        raise ValueError("data.test_size must be between 0 and 1")
    if config.target_column in config.excluded_features:
        raise ValueError("The target column cannot be an excluded feature")
    if "duration" not in config.excluded_features:
        raise ValueError("The leakage-prone duration feature must be excluded")
    return config


def validate_data(
    data: pd.DataFrame,
    *,
    target_column: str,
    excluded_features: tuple[str, ...],
) -> None:
    """Validate the raw dataset schema and target before splitting."""
    if data.empty:
        raise ValueError("Input data must contain at least one row")

    missing_columns = EXPECTED_COLUMNS.difference(data.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"Input data is missing required columns: {missing}")

    if target_column not in data.columns:
        raise ValueError(f"Target column is missing: {target_column}")

    missing_exclusions = set(excluded_features).difference(data.columns)
    if missing_exclusions:
        missing = ", ".join(sorted(missing_exclusions))
        raise ValueError(f"Excluded features are missing: {missing}")

    if data[target_column].isna().any():
        raise ValueError("Target column must not contain missing values")

    target_values = set(data[target_column].unique())
    if target_values != EXPECTED_TARGET_VALUES:
        raise ValueError(
            "Target values must be exactly 'no' and 'yes'; received "
            f"{sorted(str(value) for value in target_values)}"
        )


def split_data(
    data: pd.DataFrame,
    *,
    target_column: str,
    excluded_features: tuple[str, ...],
    test_size: float,
    random_state: int,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Remove excluded features and create a deterministic stratified split."""
    validate_data(
        data,
        target_column=target_column,
        excluded_features=excluded_features,
    )
    prepared = data.drop(columns=list(excluded_features))
    train_data, test_data = train_test_split(
        prepared,
        test_size=test_size,
        random_state=random_state,
        stratify=prepared[target_column],
    )
    return (
        train_data.sort_index().reset_index(drop=True),
        test_data.sort_index().reset_index(drop=True),
    )


def class_counts(data: pd.DataFrame, target_column: str) -> dict[str, int]:
    """Return stable class counts for provenance metadata."""
    counts = data[target_column].value_counts().sort_index()
    return {str(label): int(count) for label, count in counts.items()}


def write_outputs(
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
    *,
    config: PreparationConfig,
    config_path: Path,
) -> dict[str, Any]:
    """Write prepared datasets and return their provenance metadata."""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    train_path = config.output_dir / "train.csv"
    test_path = config.output_dir / "test.csv"
    metadata_path = config.output_dir / "metadata.json"

    train_data.to_csv(train_path, index=False)
    test_data.to_csv(test_path, index=False)

    metadata: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "source": {
            "path": str(config.input_path),
            "sha256": sha256(config.input_path),
        },
        "configuration": {
            "path": str(config_path),
            "target_column": config.target_column,
            "excluded_features": list(config.excluded_features),
            "test_size": config.test_size,
            "random_state": config.random_state,
            "stratified": True,
        },
        "train": {
            "path": str(train_path),
            "sha256": sha256(train_path),
            "rows": len(train_data),
            "columns": len(train_data.columns),
            "class_counts": class_counts(
                train_data,
                config.target_column,
            ),
        },
        "test": {
            "path": str(test_path),
            "sha256": sha256(test_path),
            "rows": len(test_data),
            "columns": len(test_data.columns),
            "class_counts": class_counts(
                test_data,
                config.target_column,
            ),
        },
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def prepare_from_config(
    config_path: Path,
    *,
    input_path: Path | None = None,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Run the complete preparation stage from checked configuration."""
    config = load_config(config_path)
    if input_path is not None or output_dir is not None:
        config = PreparationConfig(
            input_path=input_path or config.input_path,
            output_dir=output_dir or config.output_dir,
            target_column=config.target_column,
            excluded_features=config.excluded_features,
            test_size=config.test_size,
            random_state=config.random_state,
        )
    if not config.input_path.exists():
        raise FileNotFoundError(
            f"Input dataset does not exist: {config.input_path}. "
            "Run python -m scripts.download_bank_marketing first."
        )

    raw_data = pd.read_csv(config.input_path, sep=";")
    train_data, test_data = split_data(
        raw_data,
        target_column=config.target_column,
        excluded_features=config.excluded_features,
        test_size=config.test_size,
        random_state=config.random_state,
    )
    return write_outputs(
        train_data,
        test_data,
        config=config,
        config_path=config_path,
    )


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate and split the Bank Marketing dataset."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/local.json"),
        help="Path to the checked JSON configuration.",
    )
    parser.add_argument(
        "--input-data",
        type=Path,
        default=None,
        help="Optional raw CSV override, used by Azure ML components.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=None,
        help="Optional prepared-data output override.",
    )
    return parser.parse_args()


def main() -> None:
    """Run data preparation and print a concise result."""
    args = parse_args()
    metadata = prepare_from_config(
        args.config,
        input_path=args.input_data,
        output_dir=args.output_dir,
    )
    print(
        "Prepared data: "
        f"{metadata['train']['rows']} training rows, "
        f"{metadata['test']['rows']} test rows"
    )
    print(f"Output directory: {Path(metadata['train']['path']).parent}")


if __name__ == "__main__":
    main()
