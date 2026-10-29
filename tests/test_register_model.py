"""Tests for evidence-gated Azure ML model registration."""

import json
from pathlib import Path

import pytest

from src.register_model import build_model_asset, load_release_evidence


def valid_evidence() -> dict[str, object]:
    """Return complete release evidence for a model candidate."""
    return {
        "approved": True,
        "metrics": {"roc_auc": 0.82, "recall": 0.61, "precision": 0.42},
        "provenance": {
            "run_id": "run-123",
            "model_artifact_uri": "runs:/run-123/model",
            "data_reference": "sha256:abc123",
            "source_revision": "commit-123",
            "dependency_versions": {"mlflow": "3.15.1"},
            "parameters": {"random_state": 42},
        },
    }


def test_load_release_evidence_rejects_unapproved_model(tmp_path: Path) -> None:
    evidence = valid_evidence()
    evidence["approved"] = False
    path = tmp_path / "release.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(ValueError, match="requires approved"):
        load_release_evidence(path)


def test_load_release_evidence_rejects_missing_provenance(
    tmp_path: Path,
) -> None:
    evidence = valid_evidence()
    provenance = evidence["provenance"]
    assert isinstance(provenance, dict)
    del provenance["run_id"]
    path = tmp_path / "release.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(ValueError, match="run_id"):
        load_release_evidence(path)


def test_build_model_asset_preserves_governance_metadata(
    tmp_path: Path,
) -> None:
    model_path = tmp_path / "model"
    model_path.mkdir()

    model = build_model_asset(
        model_path,
        name="bank-marketing",
        evidence=valid_evidence(),
    )

    assert model.name == "bank-marketing"
    assert model.tags["lifecycle_stage"] == "candidate"
    assert model.tags["task_type"] == "classification"
    assert model.tags["mlflow_run_id"] == "run-123"
    assert '"roc_auc": 0.82' in model.properties["evaluation_metrics"]


def test_load_release_evidence_rejects_task_metric_mismatch(
    tmp_path: Path,
) -> None:
    evidence = valid_evidence()
    evidence["task_type"] = "regression"
    path = tmp_path / "release.json"
    path.write_text(json.dumps(evidence), encoding="utf-8")

    with pytest.raises(ValueError, match="regression release evidence"):
        load_release_evidence(path)
