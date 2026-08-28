"""Tests for deterministic data preparation."""

import json
from pathlib import Path

import pandas as pd
import pytest

from src.prepare_data import (
    EXPECTED_COLUMNS,
    load_config,
    split_data,
)


def sample_data(rows_per_class: int = 5) -> pd.DataFrame:
    """Create a minimal valid Bank Marketing-shaped dataset."""
    rows = rows_per_class * 2
    data: dict[str, list[object]] = {}
    for column in EXPECTED_COLUMNS:
        if column == "y":
            data[column] = ["no"] * rows_per_class + ["yes"] * rows_per_class
        elif column in {
            "job",
            "marital",
            "education",
            "default",
            "housing",
            "loan",
            "contact",
            "month",
            "day_of_week",
            "poutcome",
        }:
            data[column] = ["known"] * rows
        else:
            data[column] = list(range(rows))
    return pd.DataFrame(data)


def test_split_data_is_deterministic_and_excludes_duration() -> None:
    data = sample_data()

    first_train, first_test = split_data(
        data,
        target_column="y",
        excluded_features=("duration",),
        test_size=0.2,
        random_state=42,
    )
    second_train, second_test = split_data(
        data,
        target_column="y",
        excluded_features=("duration",),
        test_size=0.2,
        random_state=42,
    )

    pd.testing.assert_frame_equal(first_train, second_train)
    pd.testing.assert_frame_equal(first_test, second_test)
    assert "duration" not in first_train.columns
    assert first_test["y"].value_counts().to_dict() == {"no": 1, "yes": 1}


def test_split_data_rejects_missing_required_column() -> None:
    data = sample_data().drop(columns=["age"])

    with pytest.raises(ValueError, match="missing required columns: age"):
        split_data(
            data,
            target_column="y",
            excluded_features=("duration",),
            test_size=0.2,
            random_state=42,
        )


def test_split_data_rejects_unexpected_target_values() -> None:
    data = sample_data()
    data.loc[0, "y"] = "maybe"

    with pytest.raises(ValueError, match="Target values must be exactly"):
        split_data(
            data,
            target_column="y",
            excluded_features=("duration",),
            test_size=0.2,
            random_state=42,
        )


def test_load_config_requires_duration_exclusion(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "data": {
                    "input_path": "raw.csv",
                    "output_dir": "prepared",
                    "target_column": "y",
                    "excluded_features": [],
                    "test_size": 0.2,
                    "random_state": 42,
                }
            }
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="duration feature must be excluded"):
        load_config(config_path)
