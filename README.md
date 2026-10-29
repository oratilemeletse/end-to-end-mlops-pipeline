# Customer Intelligence & End-to-End MLOps Platform

## Overview

This portfolio project demonstrates how a model moves from reproducible local
training through experiment tracking, governed registration, Azure Machine
Learning deployment, monitoring, and retraining.

The platform now contains three locally verified model lifecycles:

- Bank Marketing subscription classification.
- Next-30-day Online Retail customer-spending regression.
- RFM Online Retail customer segmentation with clustering.

The [customer-intelligence extension record](docs/CUSTOMER_INTELLIGENCE_EXTENSION.md)
separates the new retail work from the reused classification, MLflow, Docker,
pytest, CI, and Azure ML foundation. Azure definitions are implemented and
offline-tested; the retail jobs and deployments have not been run in Azure.

## Problem Statement

Create a repeatable delivery path in which every model version can be traced to
its code, data reference, parameters, metrics, environment, and artifact. The
target implementation combines AI-300 MLOps coverage with production practices
used by engineering teams.

The beginner-friendly execution order, current progress, and checkpoints are
in [the project phase guide](docs/PROJECT_PHASES.md). Use that document as the
main entry point before the more detailed
[AI-300 MLOps roadmap](docs/AI300_MLOPS_ROADMAP.md).

The phase → step → granular-task record, including what was done, why, evidence,
and remaining live gates, is in the
[hierarchical implementation record](docs/IMPLEMENTATION_RECORD.md).

Start the implementation with the
[Phase 1 local MLOps tutorial](docs/PHASE1_TUTORIAL.md).

The selected learning problem and data are documented in
[the ML problem definition](docs/ML_PROBLEM.md) and
[the dataset guide](data/README.md).
Retail model limitations and evidence are in the
[spending regression](docs/models/retail-spending-regression.md) and
[customer segmentation](docs/models/retail-customer-segmentation.md) model
cards.

## Tech Stack

- Azure Machine Learning and `azure-ai-ml`
- MLflow experiment tracking and model packaging
- scikit-learn and pandas
- Docker
- GitHub Actions and pytest

## Repository Structure

```text
.
|-- .github/
|   |-- copilot-instructions.md
|   `-- workflows/ci.yml
|-- docker/
|   `-- Dockerfile
|-- components/
|   |-- environment/conda.yml
|   `-- register_model/run.py
|-- deployment/
|   |-- online/score.py
|   |-- batch/score.py
|   |-- configs/
|   |-- manage_endpoints.py
|   `-- release.py
|-- data/
|   `-- README.md
|-- docs/
|   |-- AI300_MLOPS_ROADMAP.md
|   |-- ML_PROBLEM.md
|   |-- PROJECT_PHASES.md
|   |-- PHASE1_TUTORIAL.md
|   |-- IMPLEMENTATION_RECORD.md
|   |-- architecture.md
|   |-- model-governance.md
|   `-- operations.md
|-- pipelines/
|   |-- azureml_pipeline.py
|   |-- register_assets.py
|   |-- run_customer_intelligence.py
|   |-- run_customer_monitoring.py
|   |-- submit_pipeline.py
|   `-- run_local.py
|-- src/
|   |-- customer_intelligence_data.py
|   |-- customer_intelligence_regression.py
|   |-- customer_intelligence_clustering.py
|   |-- customer_intelligence_monitoring.py
|   |-- evaluate.py
|   |-- register_model.py
|   `-- train.py
|-- tests/
|   `-- test_train.py
|-- .gitignore
|-- pyproject.toml
`-- requirements.txt
```

## Setup

Python 3.11 is required and CI uses Python 3.11.9.

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install ".[dev]"
```

Download and verify both public datasets:

```powershell
python -m scripts.download_bank_marketing
python -m scripts.download_online_retail
```

Create a deterministic, stratified train/test split:

```powershell
python -m src.prepare_data --config configs/local.json
```

Train the mixed-feature logistic-regression baseline and save it in MLflow
model format:

```powershell
python -m src.train --config configs/local.json
```

Evaluate the saved model against the untouched test set:

```powershell
python -m src.evaluate --config configs/local.json
```

Run preparation, training, evaluation, and MLflow tracking as one local
classification lifecycle:

```powershell
python -m pipelines.run_local --config configs/local.json
```

Run retail preparation, spending regression, customer segmentation, evaluation,
release evidence, and MLflow tracking:

```powershell
python -m pipelines.run_customer_intelligence `
  --config configs\customer_intelligence.json
```

Replay task-specific drift and quality monitoring over historical windows:

```powershell
python -m pipelines.run_customer_monitoring `
  --customer-config configs\customer_intelligence.json `
  --monitoring-config configs\customer_monitoring.json
```

Build the pinned, non-root local container:

```powershell
docker build --file docker\Dockerfile --tag mlops-pipeline:local .
```

Run the lifecycle in the container while keeping raw data outside the image:

```powershell
$root = (Get-Location).Path
docker run --rm `
  -v "${root}\data\raw:/app/data/raw:ro" `
  -v "${root}\artifacts:/app/artifacts" `
  mlops-pipeline:local
```

Run the retail lifecycle through the same image:

```powershell
$root = (Get-Location).Path
docker run --rm `
  -v "${root}\data\raw:/app/data/raw:ro" `
  -v "${root}\artifacts:/app/artifacts" `
  mlops-pipeline:local `
  python -m pipelines.run_customer_intelligence `
  --config configs\customer_intelligence.json
```

If public PyPI is unavailable in a managed network, pass the approved internal
Python package index with `--build-arg PIP_INDEX_URL=<approved-index-url>`.

Inspect the tracked runs locally:

```powershell
mlflow ui --backend-store-uri sqlite:///mlflow.db
```

For Azure ML operations, authenticate with Azure CLI or another credential
supported by `DefaultAzureCredential`, then provide the non-secret workspace
identifiers:

```powershell
$env:AZURE_SUBSCRIPTION_ID = "<subscription-id>"
$env:AZURE_RESOURCE_GROUP = "<resource-group>"
$env:AZURE_ML_WORKSPACE = "<workspace-name>"
```

Register immutable data and environment versions:

```powershell
python -m pipelines.register_assets `
  --data-path data\raw\bank-additional-full.csv `
  --data-version <csv-sha256-or-release-version> `
  --environment-version <source-release-version>
```

Submit the governed Azure ML pipeline:

```powershell
python -m pipelines.submit_pipeline `
  --data-asset azureml:bank-marketing-raw:<version> `
  --environment azureml:mlops-runtime:<version> `
  --compute <compute-name>
```

For customer intelligence, register `data\raw\online-retail.csv` with
`--task-type customer-intelligence`, then submit both task branches:

```powershell
python -m pipelines.submit_pipeline `
  --pipeline-task customer-intelligence `
  --data-asset azureml:online-retail-raw:<version> `
  --environment azureml:mlops-runtime:<version> `
  --compute <compute-name> `
  --regression-model-name retail-spending-regression `
  --clustering-model-name retail-customer-segmentation `
  --experiment-name customer-intelligence-release-candidates
```

This command constructs and submits cost-bearing Azure work. Run it only in an
authorized workspace after reviewing the immutable asset versions.

Deployment, canary, rollback, monitoring, private-network runner, and cleanup
procedures are documented in [the operations runbook](docs/operations.md).
The narrow, temporary dependency-audit exception is documented in
[the dependency security record](docs/dependency-security.md).

## Usage

1. Run the classification lifecycle independently from retail customer data.
2. Build leakage-safe retail snapshots with 90-day history and 30-day outcomes.
3. Select and evaluate regression candidates on chronological validation/test data.
4. evaluate clustering with silhouette, Davies-Bouldin, size, and stability gates.
5. Track task-specific parameters, metrics, lineage, models, and release evidence.
6. Score approved retail models through separate regression and clustering contracts.
7. Monitor feature drift and task quality without bypassing evaluation/release gates.
8. Register versioned assets and submit governed Azure ML pipelines when authorized.

## Learning Objectives

- Design reproducible training and evaluation stages with clear inputs and outputs.
- Use MLflow for experiment tracking, model packaging, and run comparison.
- Select and log model evaluation metrics that reflect the business objective.
- Apply MLOps practices including CI, environment reproducibility, registration, and traceability.

## Delivery Model

Follow the ordered phases and do not advance until the checkpoints for the
current phase pass:

1. Understand the project and acquire trustworthy data.
2. Prepare the data and train the local baseline.
3. Evaluate, approve, and track the model with MLflow.
4. Reproduce the environment with pinned dependencies, CI, and Docker.
5. Provision Azure ML and create versioned assets and components.
6. Run, govern, register, and deploy models.
7. Add safe releases, rollback, monitoring, retraining, and production CI/CD.

See [Project Phases and Checkpoints](docs/PROJECT_PHASES.md) for the baseline
learning sequence and
[Customer Intelligence Extension](docs/CUSTOMER_INTELLIGENCE_EXTENSION.md)
for the incremental `CI` work.

Docker remains part of the project for reproducible runtimes and custom Azure
ML environments. Docker Compose was removed because one local container does
not require orchestration. Azure production inference will use Azure ML
managed endpoints.

## Status

The complete local lifecycle and reproducible local environment were finished
before the hierarchical documentation tweak:
dependencies are pinned, quality checks run in CI, and the non-root Docker
image executes the lifecycle. Phase 7 Azure infrastructure is in progress:
the policy-aware Bicep templates build, validate, and pass development
`what-if`; the private development environment is deployed and GitHub OIDC is
verified with resource-group-scoped permissions. Cleanup verification remains
pending. Phases 8 through 14 are
implemented and locally testable, including asset registration, a governed
pipeline, evidence-gated registration, online/batch deployment definitions,
release traffic controls, monitoring decisions, CI/CD, and runbooks. They are
not marked complete because their live Azure jobs, endpoint tests, monitoring,
and rollback exercise still require an authorized deployed environment. See the
[infrastructure guide](infra/README.md), the
[policy review](docs/PHASE7_POLICY_REVIEW.md), and the
[current progress table](docs/PROJECT_PHASES.md#current-progress).

The customer-intelligence extension is locally verified. Two independent
tracked runs produced identical prepared-data hashes, regression metrics, and
clustering metrics. The approved temporal regression candidate achieved
MAE `311.29` GBP versus baseline MAE `324.91` GBP; the approved two-cluster
segmentation achieved silhouette `0.4358`, Davies-Bouldin `0.9327`, minimum
cluster fraction `0.3885`, and stability `1.0`. Historical monitoring replay
raised no alert. Live Azure retail jobs, registration, batch deployment,
scoring, and monitoring remain pending explicit authorization and cost
approval.
