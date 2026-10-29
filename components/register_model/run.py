"""Azure ML component entry point for evidence-gated registration."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from src.register_model import register_model


def build_cloud_evidence(
    evaluation_dir: Path,
    *,
    run_id: str,
    model_artifact_uri: str,
    data_reference: str,
    source_revision: str,
) -> dict[str, Any]:
    """Combine evaluation output with explicit cloud provenance."""
    report_path = evaluation_dir / "evaluation_report.json"
    if not report_path.exists():
        raise FileNotFoundError(f"Evaluation report does not exist: {report_path}")
    report = json.loads(report_path.read_text(encoding="utf-8"))
    return {
        "schema_version": "2.0",
        "task_type": report.get("task_type", "classification"),
        "approved": report.get("approved"),
        "metrics": report.get("metrics"),
        "threshold_checks": report.get("threshold_checks"),
        "provenance": {
            "run_id": run_id,
            "model_artifact_uri": model_artifact_uri,
            "data_reference": data_reference,
            "source_revision": source_revision,
            "dependency_versions": {"environment": "azureml:mlops-runtime@latest"},
            "parameters": {
                "task_type": report.get("task_type", "classification"),
                "thresholds": report.get("thresholds"),
            },
            "feature_columns": report.get("feature_columns"),
        },
    }


def parse_args() -> argparse.Namespace:
    """Parse the component contract."""
    parser = argparse.ArgumentParser()
    parser.add_argument("--model-input", type=Path, required=True)
    parser.add_argument("--evaluation-input", type=Path, required=True)
    parser.add_argument("--evidence-output", type=Path, required=True)
    parser.add_argument("--model-name", required=True)
    parser.add_argument("--subscription-id", required=True)
    parser.add_argument("--resource-group", required=True)
    parser.add_argument("--workspace-name", required=True)
    parser.add_argument("--data-reference", required=True)
    parser.add_argument("--source-revision", required=True)
    return parser.parse_args()


def main() -> None:
    """Validate evidence, register the model, and persist registration output."""
    args = parse_args()
    run_id = os.getenv("AZUREML_ROOT_RUN_ID", "").strip()
    if not run_id:
        raise ValueError("AZUREML_ROOT_RUN_ID is required for registration provenance")
    evidence = build_cloud_evidence(
        args.evaluation_input,
        run_id=run_id,
        model_artifact_uri=f"azureml://jobs/{run_id}/outputs/model",
        data_reference=args.data_reference,
        source_revision=args.source_revision,
    )
    args.evidence_output.mkdir(parents=True, exist_ok=True)
    evidence_path = args.evidence_output / "release_candidate.json"
    evidence_path.write_text(
        json.dumps(evidence, indent=2) + "\n",
        encoding="utf-8",
    )
    registered = register_model(
        args.model_input,
        evidence_path=evidence_path,
        name=args.model_name,
        subscription_id=args.subscription_id,
        resource_group=args.resource_group,
        workspace_name=args.workspace_name,
    )
    result = {
        "name": registered.name,
        "version": registered.version,
        "lifecycle_stage": registered.tags["lifecycle_stage"],
    }
    (args.evidence_output / "registration.json").write_text(
        json.dumps(result, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
