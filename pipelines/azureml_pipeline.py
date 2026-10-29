"""Construct the governed Azure ML training and registration pipeline."""

from __future__ import annotations

import shlex
from pathlib import Path
from typing import Any

from azure.ai.ml import Input, Output, command, dsl
from azure.ai.ml.entities import PipelineJob

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def build_training_pipeline(
    *,
    raw_data_uri: str,
    environment: str,
    compute: str,
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    model_name: str,
    source_revision: str,
    config_path: str = "configs/local.json",
) -> PipelineJob:
    """Build a four-stage pipeline with evaluation-gated registration."""
    prepare_data = command(
        name="prepare_bank_marketing_data",
        display_name="Prepare Bank Marketing data",
        code=str(PROJECT_ROOT),
        command=(
            "python -m src.prepare_data "
            "--input-data ${{inputs.raw_data}} "
            "--config ${{inputs.config}} "
            "--output-dir ${{outputs.prepared_data}}"
        ),
        inputs={
            "raw_data": Input(type="uri_file"),
            "config": Input(type="uri_file"),
        },
        outputs={"prepared_data": Output(type="uri_folder")},
        environment=environment,
        compute=compute,
    )
    train_model = command(
        name="train_baseline_model",
        display_name="Train baseline model",
        code=str(PROJECT_ROOT),
        command=(
            "python -m src.train "
            "--training-data ${{inputs.prepared_data}} "
            "--config ${{inputs.config}} "
            "--model-output ${{outputs.model_output}}"
        ),
        inputs={
            "prepared_data": Input(type="uri_folder"),
            "config": Input(type="uri_file"),
        },
        outputs={"model_output": Output(type="mlflow_model")},
        environment=environment,
        compute=compute,
    )
    evaluate_model = command(
        name="evaluate_model_candidate",
        display_name="Evaluate model candidate",
        code=str(PROJECT_ROOT),
        command=(
            "python -m src.evaluate "
            "--model-input ${{inputs.model_input}} "
            "--test-data ${{inputs.prepared_data}} "
            "--config ${{inputs.config}} "
            "--evaluation-output ${{outputs.evaluation_output}}"
        ),
        inputs={
            "model_input": Input(type="mlflow_model"),
            "prepared_data": Input(type="uri_folder"),
            "config": Input(type="uri_file"),
        },
        outputs={"evaluation_output": Output(type="uri_folder")},
        environment=environment,
        compute=compute,
    )
    register_model = command(
        name="register_approved_model",
        display_name="Register approved model",
        code=str(PROJECT_ROOT),
        command=(
            "python -m components.register_model.run "
            "--model-input ${{inputs.model_input}} "
            "--evaluation-input ${{inputs.evaluation_input}} "
            "--evidence-output ${{outputs.registration_evidence}} "
            "--model-name ${{inputs.model_name}} "
            "--subscription-id ${{inputs.subscription_id}} "
            "--resource-group ${{inputs.resource_group}} "
            "--workspace-name ${{inputs.workspace_name}} "
            "--data-reference ${{inputs.data_reference}} "
            "--source-revision ${{inputs.source_revision}}"
        ),
        inputs={
            "model_input": Input(type="mlflow_model"),
            "evaluation_input": Input(type="uri_folder"),
            "model_name": Input(type="string"),
            "subscription_id": Input(type="string"),
            "resource_group": Input(type="string"),
            "workspace_name": Input(type="string"),
            "data_reference": Input(type="string"),
            "source_revision": Input(type="string"),
        },
        outputs={"registration_evidence": Output(type="uri_folder")},
        environment=environment,
        compute=compute,
    )

    @dsl.pipeline(
        name="run_governed_training_pipeline",
        description="Prepare, train, evaluate, and register an approved model.",
        default_compute=compute,
    )
    def training_pipeline() -> dict[str, Any]:
        prepared = prepare_data(
            raw_data=Input(type="uri_file", path=raw_data_uri),
            config=Input(type="uri_file", path=config_path),
        )
        trained = train_model(
            prepared_data=prepared.outputs.prepared_data,
            config=Input(type="uri_file", path=config_path),
        )
        evaluated = evaluate_model(
            model_input=trained.outputs.model_output,
            prepared_data=prepared.outputs.prepared_data,
            config=Input(type="uri_file", path=config_path),
        )
        registered = register_model(
            model_input=trained.outputs.model_output,
            evaluation_input=evaluated.outputs.evaluation_output,
            model_name=model_name,
            subscription_id=subscription_id,
            resource_group=resource_group,
            workspace_name=workspace_name,
            data_reference=raw_data_uri,
            source_revision=source_revision,
        )
        return {
            "model": trained.outputs.model_output,
            "evaluation": evaluated.outputs.evaluation_output,
            "registration": registered.outputs.registration_evidence,
        }

    pipeline = training_pipeline()
    pipeline.settings.default_compute = compute
    pipeline.settings.force_rerun = False
    return pipeline


def build_customer_intelligence_pipeline(
    *,
    raw_data_uri: str,
    environment: str,
    compute: str,
    subscription_id: str,
    resource_group: str,
    workspace_name: str,
    regression_model_name: str,
    clustering_model_name: str,
    source_revision: str,
    config_path: str = "configs/customer_intelligence.json",
    source_repository: str | None = None,
    source_ref: str | None = None,
) -> PipelineJob:
    """Build governed retail regression and clustering branches."""
    if bool(source_repository) != bool(source_ref):
        raise ValueError(
            "source_repository and source_ref must be provided together"
        )
    component_code = None if source_repository else str(PROJECT_ROOT)
    command_prefix = ""
    if source_repository and source_ref:
        command_prefix = (
            "rm -rf /tmp/mlops-source && "
            f"git clone --depth 1 --branch {shlex.quote(source_ref)} "
            f"{shlex.quote(source_repository)} /tmp/mlops-source && "
            "cd /tmp/mlops-source && "
        )
    prepare_retail = command(
        name="prepare_retail_customer_data",
        display_name="Prepare retail customer snapshots",
        code=component_code,
        command=(
            f"{command_prefix}python -m scripts.download_online_retail "
            "--archive ${{inputs.raw_data}} "
            "--output /tmp/online-retail.csv && "
            "python -m src.customer_intelligence_data "
            "--input-data /tmp/online-retail.csv "
            "--config ${{inputs.config}} "
            "--output-dir ${{outputs.prepared_data}}"
        ),
        inputs={
            "raw_data": Input(type="uri_file"),
            "config": Input(type="uri_file"),
        },
        outputs={"prepared_data": Output(type="uri_folder")},
        environment=environment,
        compute=compute,
    )
    train_regression = command(
        name="train_customer_spending_regression",
        display_name="Train customer spending regression",
        code=component_code,
        command=(
            f"{command_prefix}python -m src.train_customer_regression "
            "--prepared-data ${{inputs.prepared_data}} "
            "--config ${{inputs.config}} "
            "--model-output ${{outputs.model_output}}"
        ),
        inputs={
            "prepared_data": Input(type="uri_folder"),
            "config": Input(type="uri_file"),
        },
        outputs={"model_output": Output(type="mlflow_model")},
        environment=environment,
        compute=compute,
    )
    evaluate_regression = command(
        name="evaluate_customer_spending_regression",
        display_name="Evaluate customer spending regression",
        code=component_code,
        command=(
            f"{command_prefix}python -m src.evaluate_customer_regression "
            "--model-input ${{inputs.model_input}} "
            "--prepared-data ${{inputs.prepared_data}} "
            "--config ${{inputs.config}} "
            "--evaluation-output ${{outputs.evaluation_output}}"
        ),
        inputs={
            "model_input": Input(type="mlflow_model"),
            "prepared_data": Input(type="uri_folder"),
            "config": Input(type="uri_file"),
        },
        outputs={"evaluation_output": Output(type="uri_folder")},
        environment=environment,
        compute=compute,
    )
    train_clustering = command(
        name="train_customer_segmentation",
        display_name="Train customer segmentation",
        code=component_code,
        command=(
            f"{command_prefix}python -m src.train_customer_clustering "
            "--prepared-data ${{inputs.prepared_data}} "
            "--config ${{inputs.config}} "
            "--model-output ${{outputs.model_output}}"
        ),
        inputs={
            "prepared_data": Input(type="uri_folder"),
            "config": Input(type="uri_file"),
        },
        outputs={"model_output": Output(type="mlflow_model")},
        environment=environment,
        compute=compute,
    )
    evaluate_clustering = command(
        name="evaluate_customer_segmentation",
        display_name="Evaluate customer segmentation",
        code=component_code,
        command=(
            f"{command_prefix}python -m src.evaluate_customer_clustering "
            "--model-input ${{inputs.model_input}} "
            "--prepared-data ${{inputs.prepared_data}} "
            "--config ${{inputs.config}} "
            "--evaluation-output ${{outputs.evaluation_output}}"
        ),
        inputs={
            "model_input": Input(type="mlflow_model"),
            "prepared_data": Input(type="uri_folder"),
            "config": Input(type="uri_file"),
        },
        outputs={"evaluation_output": Output(type="uri_folder")},
        environment=environment,
        compute=compute,
    )
    register_task_model = command(
        name="register_customer_intelligence_model",
        display_name="Register approved customer-intelligence model",
        code=component_code,
        command=(
            f"{command_prefix}python -m components.register_model.run "
            "--model-input ${{inputs.model_input}} "
            "--evaluation-input ${{inputs.evaluation_input}} "
            "--evidence-output ${{outputs.registration_evidence}} "
            "--model-name ${{inputs.model_name}} "
            "--subscription-id ${{inputs.subscription_id}} "
            "--resource-group ${{inputs.resource_group}} "
            "--workspace-name ${{inputs.workspace_name}} "
            "--data-reference ${{inputs.data_reference}} "
            "--source-revision ${{inputs.source_revision}}"
        ),
        inputs={
            "model_input": Input(type="mlflow_model"),
            "evaluation_input": Input(type="uri_folder"),
            "model_name": Input(type="string"),
            "subscription_id": Input(type="string"),
            "resource_group": Input(type="string"),
            "workspace_name": Input(type="string"),
            "data_reference": Input(type="string"),
            "source_revision": Input(type="string"),
        },
        outputs={"registration_evidence": Output(type="uri_folder")},
        environment=environment,
        compute=compute,
    )

    @dsl.pipeline(
        name="run_customer_intelligence_pipeline",
        description=(
            "Prepare retail snapshots, train and evaluate regression and "
            "clustering, then register approved candidates."
        ),
        default_compute=compute,
    )
    def customer_intelligence_pipeline() -> dict[str, Any]:
        prepared = prepare_retail(
            raw_data=Input(type="uri_file", path=raw_data_uri),
            config=Input(type="uri_file", path=config_path),
        )
        regression_trained = train_regression(
            prepared_data=prepared.outputs.prepared_data,
            config=Input(type="uri_file", path=config_path),
        )
        regression_evaluated = evaluate_regression(
            model_input=regression_trained.outputs.model_output,
            prepared_data=prepared.outputs.prepared_data,
            config=Input(type="uri_file", path=config_path),
        )
        regression_registered = register_task_model(
            model_input=regression_trained.outputs.model_output,
            evaluation_input=regression_evaluated.outputs.evaluation_output,
            model_name=regression_model_name,
            subscription_id=subscription_id,
            resource_group=resource_group,
            workspace_name=workspace_name,
            data_reference=raw_data_uri,
            source_revision=source_revision,
        )
        clustering_trained = train_clustering(
            prepared_data=prepared.outputs.prepared_data,
            config=Input(type="uri_file", path=config_path),
        )
        clustering_evaluated = evaluate_clustering(
            model_input=clustering_trained.outputs.model_output,
            prepared_data=prepared.outputs.prepared_data,
            config=Input(type="uri_file", path=config_path),
        )
        clustering_registered = register_task_model(
            model_input=clustering_trained.outputs.model_output,
            evaluation_input=clustering_evaluated.outputs.evaluation_output,
            model_name=clustering_model_name,
            subscription_id=subscription_id,
            resource_group=resource_group,
            workspace_name=workspace_name,
            data_reference=raw_data_uri,
            source_revision=source_revision,
        )
        return {
            "regression_model": regression_trained.outputs.model_output,
            "regression_evaluation": (regression_evaluated.outputs.evaluation_output),
            "regression_registration": (
                regression_registered.outputs.registration_evidence
            ),
            "clustering_model": clustering_trained.outputs.model_output,
            "clustering_evaluation": (clustering_evaluated.outputs.evaluation_output),
            "clustering_registration": (
                clustering_registered.outputs.registration_evidence
            ),
        }

    pipeline = customer_intelligence_pipeline()
    pipeline.settings.default_compute = compute
    pipeline.settings.force_rerun = False
    return pipeline
