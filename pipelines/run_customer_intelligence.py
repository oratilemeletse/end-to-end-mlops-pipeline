"""Run regression and clustering as tracked customer-intelligence lifecycles."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import mlflow

from pipelines.run_local import dependency_versions, git_provenance
from src.customer_intelligence_clustering import (
    evaluate_clustering_from_paths,
    load_clustering_config,
    train_clustering_from_paths,
)
from src.customer_intelligence_data import prepare_customer_intelligence_data
from src.customer_intelligence_regression import (
    evaluate_regression_from_paths,
    load_regression_config,
    train_regression_from_paths,
)
from src.customer_intelligence_release import build_release_evidence


def flatten_mapping(
    values: Mapping[str, Any],
    *,
    prefix: str = "",
) -> dict[str, str | int | float | bool]:
    """Flatten nested run parameters into MLflow-compatible scalars."""
    flattened: dict[str, str | int | float | bool] = {}
    for name, value in values.items():
        key = f"{prefix}.{name}" if prefix else str(name)
        if isinstance(value, Mapping):
            flattened.update(flatten_mapping(value, prefix=key))
        elif isinstance(value, (list, tuple)):
            flattened[key] = json.dumps(value)
        elif value is None:
            flattened[key] = "null"
        elif isinstance(value, (str, int, float, bool)):
            flattened[key] = value
        else:
            flattened[key] = str(value)
    return flattened


def _write_release_evidence(
    *,
    task_type: str,
    report: dict[str, Any],
    training_metadata: dict[str, Any],
    preparation_metadata: dict[str, Any],
    run_id: str,
    source: dict[str, Any],
    evaluation_dir: Path,
    config_path: Path,
) -> dict[str, Any]:
    """Persist release evidence for one tracked task."""
    evidence = build_release_evidence(
        task_type=task_type,
        report=report,
        training_metadata=training_metadata,
        preparation_metadata=preparation_metadata,
        run_id=run_id,
        source_revision=str(source["revision"]),
        source_dirty=bool(source["dirty"]),
        dependency_versions=dependency_versions(),
        model_artifact_uri=f"runs:/{run_id}/model",
        configuration_path=config_path,
    )
    (evaluation_dir / "release_candidate.json").write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )
    return evidence


def _track_task(
    *,
    task_type: str,
    run_name: str,
    model_dir: Path,
    evaluation_dir: Path,
    training_metadata: dict[str, Any],
    report: dict[str, Any],
    preparation_metadata: dict[str, Any],
    config_path: Path,
) -> str:
    """Track one complete task and return its MLflow run ID."""
    source = git_provenance()
    with mlflow.start_run(run_name=run_name) as run:
        mlflow.set_tags(
            {
                "lifecycle_stage": "release_candidate",
                "task_type": task_type,
                "source_revision": source["revision"],
                "source_dirty": str(source["dirty"]).lower(),
                "platform": "customer_intelligence",
            }
        )
        parameters = flatten_mapping(training_metadata.get("parameters", {}))
        parameters.update(
            {
                f"dependency.{name}": version
                for name, version in dependency_versions().items()
            }
        )
        mlflow.log_params(parameters)
        mlflow.log_metrics(
            {
                name: float(value)
                for name, value in report["metrics"].items()
                if isinstance(value, (int, float))
            }
        )
        mlflow.log_metric("approved", 1.0 if report["approved"] else 0.0)
        _write_release_evidence(
            task_type=task_type,
            report=report,
            training_metadata=training_metadata,
            preparation_metadata=preparation_metadata,
            run_id=run.info.run_id,
            source=source,
            evaluation_dir=evaluation_dir,
            config_path=config_path,
        )
        mlflow.log_artifact(
            str(Path(preparation_metadata["configuration"]["path"])),
            artifact_path="configuration",
        )
        mlflow.log_artifact(
            str(
                Path(preparation_metadata["artifacts"]["train"]["path"]).parent
                / "metadata.json"
            ),
            artifact_path="preparation",
        )
        mlflow.log_artifacts(str(evaluation_dir), artifact_path="evaluation")
        mlflow.log_artifacts(str(model_dir), artifact_path="model")
        return run.info.run_id


def run_customer_intelligence_lifecycle(config_path: Path) -> dict[str, str]:
    """Prepare retail data and track regression and clustering candidates."""
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    tracking = raw["tracking"]
    mlflow.set_tracking_uri(str(tracking["tracking_uri"]))
    mlflow.set_experiment(str(tracking["experiment_name"]))

    preparation = prepare_customer_intelligence_data(config_path)
    prepared_dir = Path(preparation["artifacts"]["train"]["path"]).parent

    regression_config = load_regression_config(config_path)
    regression_training = train_regression_from_paths(
        prepared_dir,
        regression_config.model_output,
        config_path,
    )
    regression_report = evaluate_regression_from_paths(
        regression_config.model_output,
        prepared_dir,
        config_path,
        regression_config.evaluation_output,
    )
    regression_run = _track_task(
        task_type="regression",
        run_name=str(tracking["regression_run_name"]),
        model_dir=regression_config.model_output,
        evaluation_dir=regression_config.evaluation_output,
        training_metadata=regression_training,
        report=regression_report,
        preparation_metadata=preparation,
        config_path=config_path,
    )

    clustering_config = load_clustering_config(config_path)
    clustering_training = train_clustering_from_paths(
        prepared_dir,
        clustering_config.model_output,
        config_path,
    )
    clustering_report = evaluate_clustering_from_paths(
        clustering_config.model_output,
        prepared_dir,
        config_path,
        clustering_config.evaluation_output,
    )
    clustering_run = _track_task(
        task_type="clustering",
        run_name=str(tracking["clustering_run_name"]),
        model_dir=clustering_config.model_output,
        evaluation_dir=clustering_config.evaluation_output,
        training_metadata=clustering_training,
        report=clustering_report,
        preparation_metadata=preparation,
        config_path=config_path,
    )
    return {
        "regression": regression_run,
        "clustering": clustering_run,
    }


def parse_args() -> argparse.Namespace:
    """Parse the customer-intelligence lifecycle command."""
    parser = argparse.ArgumentParser(
        description="Run and track retail regression and clustering."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/customer_intelligence.json"),
    )
    return parser.parse_args()


def main() -> None:
    """Run the complete local customer-intelligence lifecycle."""
    args = parse_args()
    run_ids = run_customer_intelligence_lifecycle(args.config)
    print(f"Regression MLflow run ID: {run_ids['regression']}")
    print(f"Clustering MLflow run ID: {run_ids['clustering']}")


if __name__ == "__main__":
    main()
