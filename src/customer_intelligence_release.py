"""Build task-aware release evidence for customer-intelligence models."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def build_release_evidence(
    *,
    task_type: str,
    report: dict[str, Any],
    training_metadata: dict[str, Any],
    preparation_metadata: dict[str, Any],
    run_id: str,
    source_revision: str,
    source_dirty: bool,
    dependency_versions: dict[str, str],
    model_artifact_uri: str,
    configuration_path: Path,
) -> dict[str, Any]:
    """Return complete governed evidence for one task candidate."""
    if task_type not in {"regression", "clustering"}:
        raise ValueError(f"Unsupported customer-intelligence task: {task_type}")
    if report.get("task_type") != task_type:
        raise ValueError("Evaluation report task does not match release task")
    if training_metadata.get("task_type") != task_type:
        raise ValueError("Training metadata task does not match release task")
    source = preparation_metadata.get("source")
    if not isinstance(source, dict) or not source.get("sha256"):
        raise ValueError("Preparation metadata must contain the retail source hash")
    return {
        "schema_version": "2.0",
        "task_type": task_type,
        "approved": report.get("approved") is True,
        "metrics": report.get("metrics"),
        "threshold_checks": report.get("threshold_checks"),
        "provenance": {
            "run_id": run_id,
            "model_artifact_uri": model_artifact_uri,
            "data_reference": source["sha256"],
            "source_revision": source_revision,
            "source_dirty": source_dirty,
            "dependency_versions": dependency_versions,
            "parameters": training_metadata.get("parameters"),
            "feature_columns": training_metadata.get("feature_columns"),
            "configuration_path": str(configuration_path),
            "preparation_task_ids": preparation_metadata.get("task_ids"),
        },
    }
