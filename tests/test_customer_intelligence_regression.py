"""Tests for retail customer spending regression."""

import json
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from src.customer_intelligence_data import REGRESSION_FEATURES, TARGET_COLUMN
from src.customer_intelligence_regression import (
    baseline_predictions,
    load_regression_config,
    regression_metrics,
    spend_band_errors,
    validate_regression_data,
)


def regression_frame() -> pd.DataFrame:
    """Return one valid prepared regression fixture."""
    data: dict[str, object] = {
        "customer_id": ["1", "2", "3"],
        "cutoff_date": ["2024-01-01"] * 3,
        "target_window_end": ["2024-02-01"] * 3,
        TARGET_COLUMN: [0.0, 20.0, 100.0],
    }
    for index, feature in enumerate(REGRESSION_FEATURES, start=1):
        data[feature] = [float(index), float(index + 1), float(index + 2)]
    return pd.DataFrame(data)


def test_regression_metrics_are_calculated_in_original_units() -> None:
    metrics = regression_metrics(
        np.array([0.0, 10.0, 20.0]),
        np.array([0.0, 8.0, 24.0]),
    )

    assert metrics["mae"] == pytest.approx(2.0)
    assert metrics["rmse"] == pytest.approx((20.0 / 3.0) ** 0.5)
    assert metrics["r2"] == pytest.approx(0.9)


def test_history_rate_baseline_uses_configured_horizon() -> None:
    frame = regression_frame()
    frame["monetary_value_gbp"] = [90.0, 180.0, 270.0]

    predictions = baseline_predictions(
        frame,
        baseline_name="past_spend_rate",
        training_target_mean=999.0,
        history_days=90,
        horizon_days=30,
    )

    assert predictions.tolist() == [30.0, 60.0, 90.0]


def test_spend_band_errors_report_zero_and_positive_targets() -> None:
    frame = regression_frame()

    bands = spend_band_errors(
        frame[TARGET_COLUMN],
        np.array([5.0, 25.0, 80.0]),
    )

    assert bands["zero"] == {"rows": 1, "mae": 5.0}
    assert bands["lower_positive"] == {"rows": 1, "mae": 5.0}
    assert bands["higher_positive"] == {"rows": 1, "mae": 20.0}


def test_regression_data_rejects_negative_target() -> None:
    frame = regression_frame()
    frame.loc[0, TARGET_COLUMN] = -1.0

    with pytest.raises(ValueError, match="must not contain negative"):
        validate_regression_data(frame)


def test_regression_config_rejects_unknown_model(tmp_path: Path) -> None:
    source = json.loads(
        Path("configs/customer_intelligence.json").read_text(encoding="utf-8")
    )
    source["regression"]["candidate_models"] = ["unsupported"]
    path = tmp_path / "config.json"
    path.write_text(json.dumps(source), encoding="utf-8")

    with pytest.raises(ValueError, match="Unsupported regression models"):
        load_regression_config(path)
