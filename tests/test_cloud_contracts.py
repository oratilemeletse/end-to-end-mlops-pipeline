"""Offline tests for Azure ML configuration and release contracts."""

import json
from pathlib import Path

import pytest

from deployment.manage_endpoints import build_batch_resources, load_deployment_config
from deployment.online.score import parse_request
from deployment.release import build_traffic_split
from pipelines.azureml_pipeline import (
    build_customer_intelligence_pipeline,
    build_training_pipeline,
)
from src.azure_config import WorkspaceConfig
from src.monitoring import (
    MonitoringThresholds,
    population_stability_index,
    retraining_decision,
)


def test_workspace_config_requires_all_identifiers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("AZURE_SUBSCRIPTION_ID", raising=False)
    monkeypatch.delenv("AZURE_RESOURCE_GROUP", raising=False)
    monkeypatch.delenv("AZURE_ML_WORKSPACE", raising=False)

    with pytest.raises(ValueError, match="AZURE_SUBSCRIPTION_ID"):
        WorkspaceConfig.from_environment()


def test_deployment_configs_are_valid() -> None:
    for name in ("development", "staging", "production"):
        config = load_deployment_config(Path("deployment") / "configs" / f"{name}.json")
        assert config["environment"] == name


def test_customer_intelligence_batch_deployment_uses_task_scorer() -> None:
    config = load_deployment_config(Path("deployment") / "configs" / "development.json")

    endpoint, deployment = build_batch_resources(
        config,
        endpoint_name="retail-batch",
        deployment_name="candidate",
        model="azureml:retail-spending-regression:1",
        environment="azureml:mlops-runtime:1",
        compute="cpu-cluster",
        task_type="regression",
    )

    assert endpoint.tags["task_type"] == "regression"
    assert (
        deployment.code_configuration.scoring_script
        == "deployment/batch/score_regression.py"
    )


def test_governed_pipeline_wires_all_stage_outputs() -> None:
    pipeline = build_training_pipeline(
        raw_data_uri="azureml:bank-marketing-raw:1",
        environment="azureml:mlops-runtime:1",
        compute="cpu-cluster",
        subscription_id="00000000-0000-0000-0000-000000000000",
        resource_group="rg-test",
        workspace_name="ws-test",
        model_name="bank-marketing",
        source_revision="revision-123",
    )

    assert set(pipeline.jobs) == {"prepared", "trained", "evaluated", "registered"}
    assert set(pipeline.outputs) == {"model", "evaluation", "registration"}


def test_customer_intelligence_pipeline_wires_both_task_branches() -> None:
    pipeline = build_customer_intelligence_pipeline(
        raw_data_uri="azureml:online-retail-raw:1",
        environment="azureml:mlops-runtime:1",
        compute="cpu-cluster",
        subscription_id="00000000-0000-0000-0000-000000000000",
        resource_group="rg-test",
        workspace_name="ws-test",
        regression_model_name="retail-spending-regression",
        clustering_model_name="retail-customer-segmentation",
        source_revision="revision-123",
    )

    assert set(pipeline.jobs) == {
        "prepared",
        "regression_trained",
        "regression_evaluated",
        "regression_registered",
        "clustering_trained",
        "clustering_evaluated",
        "clustering_registered",
    }
    assert set(pipeline.outputs) == {
        "regression_model",
        "regression_evaluation",
        "regression_registration",
        "clustering_model",
        "clustering_evaluation",
        "clustering_registration",
    }
    prepare_command = pipeline.jobs["prepared"].component.command
    assert "scripts.download_online_retail" in prepare_command
    assert "--archive ${{inputs.raw_data}}" in prepare_command
    assert "--input-data /tmp/online-retail.csv" in prepare_command


def test_customer_intelligence_pipeline_supports_private_workspace_source() -> None:
    pipeline = build_customer_intelligence_pipeline(
        raw_data_uri="azureml:online-retail-raw:1",
        environment="azureml:mlops-runtime:1",
        compute="cpu-cluster",
        subscription_id="00000000-0000-0000-0000-000000000000",
        resource_group="rg-test",
        workspace_name="ws-test",
        regression_model_name="retail-spending-regression",
        clustering_model_name="retail-customer-segmentation",
        source_revision="revision-123",
        config_path="configs/customer_intelligence.json",
        source_repository="https://github.com/example/mlops.git",
        source_ref="deploy/release-123",
    )

    prepare_component = pipeline.jobs["prepared"].component
    assert prepare_component.code is None
    assert "git clone --depth 1 --branch deploy/release-123" in (
        prepare_component.command
    )
    assert "/tmp/mlops-source" in prepare_component.command
    assert "--config configs/customer_intelligence.json" in (
        prepare_component.command
    )
    assert "pip install --disable-pip-version-check" in prepare_component.command
    assert "config" not in prepare_component.inputs


def test_customer_intelligence_pipeline_requires_complete_source_reference() -> None:
    with pytest.raises(ValueError, match="must be provided together"):
        build_customer_intelligence_pipeline(
            raw_data_uri="azureml:online-retail-raw:1",
            environment="azureml:mlops-runtime:1",
            compute="cpu-cluster",
            subscription_id="00000000-0000-0000-0000-000000000000",
            resource_group="rg-test",
            workspace_name="ws-test",
            regression_model_name="retail-spending-regression",
            clustering_model_name="retail-customer-segmentation",
            source_revision="revision-123",
            source_repository="https://github.com/example/mlops.git",
        )


def test_online_request_rejects_leakage_feature() -> None:
    request = json.dumps({"input_data": [{"age": 40, "duration": 30}]})

    with pytest.raises(ValueError, match="prohibited duration"):
        parse_request(request)


def test_release_split_supports_canary_promotion_and_rollback() -> None:
    assert build_traffic_split(
        candidate="green",
        candidate_percentage=10,
        stable="blue",
    ) == {"green": 10, "blue": 90}
    assert build_traffic_split(
        candidate="green",
        candidate_percentage=100,
        stable="blue",
    ) == {"green": 100}
    assert build_traffic_split(
        candidate="green",
        candidate_percentage=0,
        stable="blue",
    ) == {"blue": 100}


def test_monitoring_requires_governed_retraining() -> None:
    psi = population_stability_index([80, 20], [50, 50])
    decision = retraining_decision(
        drift_scores={"age": psi},
        quality_metrics={"roc_auc": 0.7, "recall": 0.6},
        thresholds=MonitoringThresholds(
            maximum_psi=0.2,
            minimum_roc_auc=0.75,
            minimum_recall=0.5,
        ),
    )

    assert decision["alert"] is True
    assert decision["retraining_required"] is True
    assert decision["release_gate_required"] is True
    assert set(decision["reasons"]) == {"drift:age", "quality:roc_auc"}
