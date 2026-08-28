"""Evaluate a saved model and apply configured release thresholds."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


class BinaryClassifier(Protocol):
    """Interface required by the evaluation helper."""

    classes_: np.ndarray

    def predict_proba(self, features: pd.DataFrame) -> np.ndarray:
        """Return probabilities for each class."""


@dataclass(frozen=True)
class EvaluationConfig:
    """Validated settings for evaluation and approval."""

    target_column: str
    output_dir: Path
    decision_threshold: float
    minimum_roc_auc: float
    minimum_recall: float
    minimum_precision: float


def load_evaluation_config(path: Path) -> EvaluationConfig:
    """Load and validate evaluation settings from checked configuration."""
    if not path.exists():
        raise FileNotFoundError(f"Configuration file does not exist: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        data = raw["data"]
        evaluation = raw["evaluation"]
        config = EvaluationConfig(
            target_column=str(data["target_column"]),
            output_dir=Path(evaluation["output_dir"]),
            decision_threshold=float(evaluation["decision_threshold"]),
            minimum_roc_auc=float(evaluation["minimum_roc_auc"]),
            minimum_recall=float(evaluation["minimum_recall"]),
            minimum_precision=float(evaluation["minimum_precision"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid evaluation configuration in {path}: {error}"
        ) from error

    for name, value in {
        "decision_threshold": config.decision_threshold,
        "minimum_roc_auc": config.minimum_roc_auc,
        "minimum_recall": config.minimum_recall,
        "minimum_precision": config.minimum_precision,
    }.items():
        if not 0 <= value <= 1:
            raise ValueError(f"evaluation.{name} must be between 0 and 1")
    return config


def positive_class_probabilities(
    model: BinaryClassifier,
    features: pd.DataFrame,
) -> np.ndarray:
    """Return probabilities for the explicit positive class label `yes`."""
    probabilities = model.predict_proba(features)
    classes = list(model.classes_)
    if probabilities.ndim != 2 or probabilities.shape[1] != len(classes):
        raise ValueError("Model returned an invalid probability matrix")
    if classes != ["no", "yes"]:
        if "yes" not in classes or len(classes) != 2:
            raise ValueError(
                "Evaluation expects binary model classes containing 'no' and 'yes'"
            )
    return probabilities[:, classes.index("yes")]


def evaluate_model(
    model: BinaryClassifier,
    features: pd.DataFrame,
    target: pd.Series,
    *,
    decision_threshold: float = 0.5,
) -> tuple[dict[str, float], dict[str, int]]:
    """Calculate threshold metrics and confusion-matrix counts."""
    if features.empty:
        raise ValueError("Evaluation features must contain at least one row")
    if len(features) != len(target):
        raise ValueError("Evaluation features and target must have the same row count")
    if set(target.unique()) != {"no", "yes"}:
        raise ValueError("Evaluation target values must be exactly 'no' and 'yes'")
    if not 0 <= decision_threshold <= 1:
        raise ValueError("decision_threshold must be between 0 and 1")

    positive_probabilities = positive_class_probabilities(model, features)
    predictions = np.where(
        positive_probabilities >= decision_threshold,
        "yes",
        "no",
    )
    tn, fp, fn, tp = confusion_matrix(
        target,
        predictions,
        labels=["no", "yes"],
    ).ravel()
    metrics = {
        "accuracy": float(accuracy_score(target, predictions)),
        "precision": float(
            precision_score(
                target,
                predictions,
                pos_label="yes",
                zero_division=0,
            )
        ),
        "recall": float(
            recall_score(
                target,
                predictions,
                pos_label="yes",
                zero_division=0,
            )
        ),
        "f1": float(
            f1_score(
                target,
                predictions,
                pos_label="yes",
                zero_division=0,
            )
        ),
        "roc_auc": float(
            roc_auc_score(
                (target == "yes").astype(int),
                positive_probabilities,
            )
        ),
    }
    counts = {
        "true_negatives": int(tn),
        "false_positives": int(fp),
        "false_negatives": int(fn),
        "true_positives": int(tp),
    }
    return metrics, counts


def approval_decision(
    metrics: dict[str, float],
    config: EvaluationConfig,
) -> tuple[bool, dict[str, bool]]:
    """Return the overall decision and each threshold result."""
    checks = {
        "roc_auc": metrics["roc_auc"] >= config.minimum_roc_auc,
        "recall": metrics["recall"] >= config.minimum_recall,
        "precision": metrics["precision"] >= config.minimum_precision,
    }
    return all(checks.values()), checks


def evaluate_from_paths(
    model_path: Path,
    test_data_path: Path,
    config_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Load the saved model, evaluate test data, and write evidence."""
    if test_data_path.is_dir():
        test_data_path = test_data_path / "test.csv"
    if not model_path.exists():
        raise FileNotFoundError(f"Model artifact does not exist: {model_path}")
    if not test_data_path.exists():
        raise FileNotFoundError(f"Test data does not exist: {test_data_path}")

    config = load_evaluation_config(config_path)
    destination = output_dir or config.output_dir
    test_data = pd.read_csv(test_data_path)
    if config.target_column not in test_data.columns:
        raise ValueError(
            f"Target column is missing from test data: {config.target_column}"
        )
    if "duration" in test_data.columns:
        raise ValueError("Test data contains prohibited leakage feature: duration")

    model = mlflow.sklearn.load_model(str(model_path))
    features = test_data.drop(columns=[config.target_column])
    target = test_data[config.target_column]
    metrics, counts = evaluate_model(
        model,
        features,
        target,
        decision_threshold=config.decision_threshold,
    )
    approved, checks = approval_decision(metrics, config)
    destination.mkdir(parents=True, exist_ok=True)

    report: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "model_path": str(model_path),
        "test_data_path": str(test_data_path),
        "test_rows": len(test_data),
        "decision_threshold": config.decision_threshold,
        "metrics": metrics,
        "confusion_matrix": counts,
        "thresholds": {
            "minimum_roc_auc": config.minimum_roc_auc,
            "minimum_recall": config.minimum_recall,
            "minimum_precision": config.minimum_precision,
        },
        "threshold_checks": checks,
        "approved": approved,
    }
    (destination / "evaluation_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "confusion_matrix.json").write_text(
        json.dumps(counts, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Evaluate the saved Bank Marketing model."
    )
    parser.add_argument(
        "--model-input",
        type=Path,
        default=Path("artifacts/model/baseline"),
    )
    parser.add_argument(
        "--test-data",
        type=Path,
        default=Path("artifacts/prepared/test.csv"),
    )
    parser.add_argument(
        "--evaluation-output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/local.json"),
    )
    return parser.parse_args()


def main() -> None:
    """Run model evaluation and print its decision."""
    args = parse_args()
    report = evaluate_from_paths(
        args.model_input,
        args.test_data,
        args.config,
        args.evaluation_output,
    )
    print(
        "Evaluation complete: "
        f"ROC-AUC={report['metrics']['roc_auc']:.4f}, "
        f"recall={report['metrics']['recall']:.4f}, "
        f"precision={report['metrics']['precision']:.4f}"
    )
    print(f"Approved: {report['approved']}")


if __name__ == "__main__":
    main()
