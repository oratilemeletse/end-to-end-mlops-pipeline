"""Run the complete local MLOps lifecycle inside one MLflow run."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import subprocess
from pathlib import Path
from typing import Any

import mlflow

from src.evaluate import evaluate_from_paths
from src.prepare_data import prepare_from_config
from src.train import load_training_config, train_from_paths


def git_provenance() -> dict[str, Any]:
    """Return source revision details without requiring a committed repository."""
    revision = "unavailable"
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            check=True,
            capture_output=True,
            text=True,
        )
        revision = result.stdout.strip()
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass

    dirty = True
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            check=True,
            capture_output=True,
            text=True,
        )
        dirty = bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.CalledProcessError):
        pass
    return {"revision": revision, "dirty": dirty}


def dependency_versions() -> dict[str, str]:
    """Return versions needed to reproduce the local run."""
    packages = ["mlflow", "numpy", "openpyxl", "pandas", "scikit-learn", "skops"]
    return {package: importlib.metadata.version(package) for package in packages}


def run_local_lifecycle(config_path: Path) -> str:
    """Prepare, train, evaluate, and track one complete local run."""
    raw = json.loads(config_path.read_text(encoding="utf-8"))
    tracking = raw["tracking"]
    mlflow.set_tracking_uri(str(tracking["tracking_uri"]))
    mlflow.set_experiment(str(tracking["experiment_name"]))

    training_config = load_training_config(config_path)
    prepared_dir = Path(raw["data"]["output_dir"])
    train_path = prepared_dir / "train.csv"
    test_path = prepared_dir / "test.csv"
    evaluation_dir = Path(raw["evaluation"]["output_dir"])

    with mlflow.start_run(run_name=str(tracking["run_name"])) as run:
        source = git_provenance()
        mlflow.set_tags(
            {
                "lifecycle_stage": "baseline",
                "source_revision": source["revision"],
                "source_dirty": str(source["dirty"]).lower(),
                "model_type": "logistic_regression",
            }
        )

        preparation = prepare_from_config(config_path)
        training = train_from_paths(
            train_path,
            training_config.model_output,
            config_path,
        )
        evaluation = evaluate_from_paths(
            training_config.model_output,
            test_path,
            config_path,
            evaluation_dir,
        )
        release_evidence = {
            "schema_version": "1.0",
            "approved": evaluation["approved"],
            "metrics": evaluation["metrics"],
            "threshold_checks": evaluation["threshold_checks"],
            "provenance": {
                "run_id": run.info.run_id,
                "model_artifact_uri": f"runs:/{run.info.run_id}/model",
                "data_reference": preparation["source"]["sha256"],
                "source_revision": source["revision"],
                "source_dirty": source["dirty"],
                "dependency_versions": dependency_versions(),
                "parameters": training["parameters"],
                "configuration_path": str(config_path),
            },
        }
        release_evidence_path = evaluation_dir / "release_candidate.json"
        release_evidence_path.write_text(
            json.dumps(release_evidence, indent=2) + "\n",
            encoding="utf-8",
        )

        parameters = {
            **training["parameters"],
            "data.random_state": preparation["configuration"]["random_state"],
            "data.test_size": preparation["configuration"]["test_size"],
            "data.source_sha256": preparation["source"]["sha256"],
            "data.train_sha256": preparation["train"]["sha256"],
            "data.test_sha256": preparation["test"]["sha256"],
            "evaluation.decision_threshold": evaluation["decision_threshold"],
        }
        for name, value in dependency_versions().items():
            parameters[f"dependency.{name}"] = value
        mlflow.log_params(parameters)
        mlflow.log_metrics(evaluation["metrics"])
        mlflow.log_metric(
            "approved",
            1.0 if evaluation["approved"] else 0.0,
        )
        mlflow.log_artifact(
            str(prepared_dir / "metadata.json"),
            artifact_path="preparation",
        )
        mlflow.log_artifacts(
            str(evaluation_dir),
            artifact_path="evaluation",
        )
        mlflow.log_artifacts(
            str(training_config.model_output),
            artifact_path="model",
        )
        mlflow.log_artifact(str(config_path), artifact_path="configuration")
        return run.info.run_id


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Run and track the complete local MLOps lifecycle."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/local.json"),
    )
    return parser.parse_args()


def main() -> None:
    """Run the lifecycle and print the MLflow run ID."""
    args = parse_args()
    run_id = run_local_lifecycle(args.config)
    print(f"Local lifecycle complete. MLflow run ID: {run_id}")


if __name__ == "__main__":
    main()
