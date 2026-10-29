"""Run deterministic historical monitoring replay for retail models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import mlflow.sklearn
import numpy as np
import pandas as pd

from src.customer_intelligence_clustering import load_clustering_config
from src.customer_intelligence_data import (
    CLUSTERING_FEATURES,
    REGRESSION_FEATURES,
    TARGET_COLUMN,
)
from src.customer_intelligence_monitoring import (
    build_numeric_reference,
    clustering_monitoring_report,
    customer_retraining_decision,
    load_customer_monitoring_config,
    numeric_drift_report,
    regression_monitoring_report,
)
from src.customer_intelligence_regression import (
    baseline_predictions,
    load_regression_config,
)


def run_monitoring_replay(
    customer_config_path: Path,
    monitoring_config_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Replay regression and clustering monitoring with historical windows."""
    customer_config = json.loads(customer_config_path.read_text(encoding="utf-8"))
    prepared_dir = Path(customer_config["retail_data"]["output_dir"])
    train = pd.read_csv(prepared_dir / "train.csv", dtype={"customer_id": "string"})
    validation = pd.read_csv(
        prepared_dir / "validation.csv",
        dtype={"customer_id": "string"},
    )
    test = pd.read_csv(prepared_dir / "test.csv", dtype={"customer_id": "string"})
    clustering = pd.read_csv(
        prepared_dir / "clustering.csv",
        dtype={"customer_id": "string"},
    )
    thresholds = load_customer_monitoring_config(monitoring_config_path)

    regression_config = load_regression_config(customer_config_path)
    regression_model = mlflow.sklearn.load_model(str(regression_config.model_output))
    regression_metadata = json.loads(
        (regression_config.model_output / "training_metadata.json").read_text(
            encoding="utf-8"
        )
    )
    regression_reference = build_numeric_reference(
        train,
        REGRESSION_FEATURES,
        histogram_bins=thresholds.histogram_bins,
    )
    regression_drift = numeric_drift_report(
        regression_reference,
        test,
        minimum_current_rows=thresholds.minimum_current_rows,
    )
    regression_predictions = np.clip(
        regression_model.predict(test[REGRESSION_FEATURES].astype(float)),
        0.0,
        None,
    )
    regression_baseline = baseline_predictions(
        test,
        baseline_name=str(regression_metadata["validation"]["selected_baseline"]),
        training_target_mean=float(regression_metadata["refit_target_mean"]),
        history_days=regression_config.history_days,
        horizon_days=regression_config.horizon_days,
    )
    regression_quality = regression_monitoring_report(
        test[TARGET_COLUMN],
        regression_predictions,
        regression_baseline,
    )
    regression_decision = customer_retraining_decision(
        task_type="regression",
        drift_report=regression_drift,
        quality_report=regression_quality,
        thresholds=thresholds,
    )

    clustering_config = load_clustering_config(customer_config_path)
    clustering_model = mlflow.sklearn.load_model(str(clustering_config.model_output))
    reference_cutoff = validation["cutoff_date"].max()
    cluster_reference_data = validation.loc[
        validation["cutoff_date"] == reference_cutoff
    ].reset_index(drop=True)
    cluster_reference = build_numeric_reference(
        cluster_reference_data,
        CLUSTERING_FEATURES,
        histogram_bins=thresholds.histogram_bins,
    )
    clustering_drift = numeric_drift_report(
        cluster_reference,
        clustering,
        minimum_current_rows=thresholds.minimum_current_rows,
    )
    reference_features = cluster_reference_data[CLUSTERING_FEATURES].astype(float)
    current_features = clustering[CLUSTERING_FEATURES].astype(float)
    reference_labels = np.asarray(
        clustering_model.predict(reference_features),
        dtype=int,
    )
    current_labels = np.asarray(
        clustering_model.predict(current_features),
        dtype=int,
    )
    reference_distances = np.asarray(
        clustering_model.transform(reference_features),
        dtype=float,
    ).min(axis=1)
    current_distances = np.asarray(
        clustering_model.transform(current_features),
        dtype=float,
    ).min(axis=1)
    clustering_quality = clustering_monitoring_report(
        reference_labels,
        current_labels,
        reference_distances,
        current_distances,
    )
    clustering_decision = customer_retraining_decision(
        task_type="clustering",
        drift_report=clustering_drift,
        quality_report=clustering_quality,
        thresholds=thresholds,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "mode": "historical_replay",
        "task_id": "CI-E.2.2",
        "regression": {
            "drift": regression_drift,
            "quality": regression_quality,
            "decision": regression_decision,
        },
        "clustering": {
            "reference_cutoff": reference_cutoff,
            "drift": clustering_drift,
            "quality": clustering_quality,
            "decision": clustering_decision,
        },
        "limitations": [
            "Historical replay validates monitoring logic but is not live telemetry.",
            "Regression quality is available only after the full outcome window matures.",
            "Clustering compares assignments from the same fixed model version.",
        ],
    }
    (output_dir / "monitoring_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "regression_reference.json").write_text(
        json.dumps(regression_reference, indent=2) + "\n",
        encoding="utf-8",
    )
    (output_dir / "clustering_reference.json").write_text(
        json.dumps(cluster_reference, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def parse_args() -> argparse.Namespace:
    """Parse historical monitoring replay arguments."""
    parser = argparse.ArgumentParser(
        description="Replay customer-intelligence drift and quality monitoring."
    )
    parser.add_argument(
        "--customer-config",
        type=Path,
        default=Path("configs/customer_intelligence.json"),
    )
    parser.add_argument(
        "--monitoring-config",
        type=Path,
        default=Path("configs/customer_monitoring.json"),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("artifacts/customer_intelligence/monitoring"),
    )
    return parser.parse_args()


def main() -> None:
    """Run and summarize historical monitoring replay."""
    args = parse_args()
    report = run_monitoring_replay(
        args.customer_config,
        args.monitoring_config,
        args.output_dir,
    )
    print(
        "Monitoring replay complete: "
        f"regression alert={report['regression']['decision']['alert']}, "
        f"clustering alert={report['clustering']['decision']['alert']}"
    )


if __name__ == "__main__":
    main()
