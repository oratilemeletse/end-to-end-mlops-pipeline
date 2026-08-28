"""Tests for model evaluation and approval."""

from pathlib import Path

import numpy as np
import pandas as pd

from src.evaluate import (
    EvaluationConfig,
    approval_decision,
    evaluate_model,
)


class FixedProbabilityModel:
    """Small deterministic classifier used to test metric logic."""

    classes_ = np.array(["no", "yes"])

    def __init__(self, positive_probabilities: list[float]) -> None:
        self.positive_probabilities = np.array(positive_probabilities)

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        positive = self.positive_probabilities[: len(features)]
        return np.column_stack((1 - positive, positive))


def config(tmp_path: Path) -> EvaluationConfig:
    """Return reusable strict evaluation settings."""
    return EvaluationConfig(
        target_column="y",
        output_dir=tmp_path,
        decision_threshold=0.5,
        minimum_roc_auc=0.75,
        minimum_recall=0.5,
        minimum_precision=0.5,
    )


def test_evaluate_model_calculates_threshold_metrics() -> None:
    features = pd.DataFrame({"feature": [1, 2, 3, 4]})
    target = pd.Series(["no", "no", "yes", "yes"])
    model = FixedProbabilityModel([0.1, 0.7, 0.8, 0.9])

    metrics, counts = evaluate_model(
        model,
        features,
        target,
        decision_threshold=0.5,
    )

    assert metrics["precision"] == 2 / 3
    assert metrics["recall"] == 1.0
    assert counts == {
        "true_negatives": 1,
        "false_positives": 1,
        "false_negatives": 0,
        "true_positives": 2,
    }


def test_approval_decision_reports_pass_and_failure(tmp_path: Path) -> None:
    evaluation_config = config(tmp_path)

    approved, passing_checks = approval_decision(
        {"roc_auc": 0.9, "recall": 0.8, "precision": 0.7},
        evaluation_config,
    )
    rejected, failing_checks = approval_decision(
        {"roc_auc": 0.9, "recall": 0.4, "precision": 0.7},
        evaluation_config,
    )

    assert approved is True
    assert all(passing_checks.values())
    assert rejected is False
    assert failing_checks["recall"] is False
