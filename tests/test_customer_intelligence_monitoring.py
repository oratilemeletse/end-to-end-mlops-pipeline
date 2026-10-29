"""Tests for task-specific customer-intelligence monitoring."""

import numpy as np
import pandas as pd
import pytest

from src.customer_intelligence_monitoring import (
    CustomerMonitoringThresholds,
    build_numeric_reference,
    clustering_monitoring_report,
    customer_retraining_decision,
    numeric_drift_report,
    regression_monitoring_report,
)


def thresholds() -> CustomerMonitoringThresholds:
    """Return monitoring thresholds for unit tests."""
    return CustomerMonitoringThresholds(
        histogram_bins=4,
        minimum_current_rows=4,
        maximum_feature_psi=0.2,
        maximum_regression_mae_to_baseline_ratio=1.0,
        maximum_cluster_assignment_psi=0.2,
        maximum_cluster_distance_ratio=1.25,
    )


def test_numeric_drift_uses_frozen_reference_buckets() -> None:
    reference_data = pd.DataFrame({"spend": [1, 2, 3, 4, 5, 6, 7, 8]})
    reference = build_numeric_reference(
        reference_data,
        ["spend"],
        histogram_bins=4,
    )
    stable = numeric_drift_report(
        reference,
        reference_data.copy(),
        minimum_current_rows=4,
    )
    shifted = numeric_drift_report(
        reference,
        pd.DataFrame({"spend": [100, 101, 102, 103]}),
        minimum_current_rows=4,
    )

    assert stable["features"]["spend"]["psi"] == pytest.approx(0.0)
    assert shifted["features"]["spend"]["psi"] > 0.2


def test_drift_rejects_insufficient_current_rows() -> None:
    reference = build_numeric_reference(
        pd.DataFrame({"spend": [1, 2, 3, 4]}),
        ["spend"],
        histogram_bins=2,
    )

    with pytest.raises(ValueError, match="insufficient rows"):
        numeric_drift_report(
            reference,
            pd.DataFrame({"spend": [1]}),
            minimum_current_rows=2,
        )


def test_regression_monitoring_compares_frozen_baseline() -> None:
    report = regression_monitoring_report(
        np.array([0.0, 10.0, 20.0]),
        np.array([0.0, 9.0, 19.0]),
        np.array([10.0, 10.0, 10.0]),
    )

    assert report["mae"] == pytest.approx(2.0 / 3.0)
    assert report["mae_to_baseline_ratio"] < 1.0


def test_clustering_monitoring_is_permutation_stable_for_fixed_ids() -> None:
    report = clustering_monitoring_report(
        np.array([0, 0, 1, 1]),
        np.array([0, 0, 1, 1]),
        np.array([1.0, 1.0, 2.0, 2.0]),
        np.array([1.0, 1.0, 2.0, 2.0]),
    )

    assert report["assignment_psi"] == pytest.approx(0.0)
    assert report["distance_ratio"] == pytest.approx(1.0)


def test_retraining_decision_never_bypasses_release_gate() -> None:
    decision = customer_retraining_decision(
        task_type="regression",
        drift_report={
            "features": {
                "spend": {"psi": 0.3},
            }
        },
        quality_report={"mae_to_baseline_ratio": 1.2},
        thresholds=thresholds(),
    )

    assert decision["alert"] is True
    assert set(decision["reasons"]) == {
        "drift:spend",
        "quality:mae_to_baseline",
    }
    assert decision["evaluation_gate_required"] is True
    assert decision["release_gate_required"] is True
