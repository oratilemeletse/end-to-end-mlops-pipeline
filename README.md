# End-to-End MLOps Pipeline

## Overview

This portfolio project demonstrates how a model moves from reproducible local
training through experiment tracking, governed registration, Azure Machine
Learning deployment, monitoring, and retraining.

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
|   |-- submit_pipeline.py
|   `-- run_local.py
|-- src/
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

Download and verify the selected public dataset:

```powershell
python -m scripts.download_bank_marketing
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
lifecycle:

```powershell
python -m pipelines.run_local --config configs/local.json
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

Deployment, canary, rollback, monitoring, private-network runner, and cleanup
procedures are documented in [the operations runbook](docs/operations.md).
The narrow, temporary dependency-audit exception is documented in
[the dependency security record](docs/dependency-security.md).

## Usage

1. Train a deterministic baseline with `src/train.py`.
2. Calculate the standard metric suite with `src/evaluate.py`.
3. Log parameters, metrics, and the model artifact through `pipelines/mlflow_tracking.py`.
4. Register versioned data and environment assets.
5. Build and submit the governed Azure ML pipeline.
6. Register only candidates with approved evaluation and complete provenance.
7. Deploy approved versions to isolated online and batch deployments.
8. Release with explicit canary traffic and a retained rollback target.
9. Monitor service and model health and route retraining through the same gates.

## Learning Objectives

- Design reproducible training and evaluation stages with clear inputs and outputs.
- Use MLflow for experiment tracking, model packaging, and run comparison.
- Select and log model evaluation metrics that reflect the business objective.
- Apply MLOps practices including CI, environment reproducibility, registration, and traceability.

## Planned Delivery

Follow the ordered phases and do not advance until the checkpoints for the
current phase pass:

1. Understand the project and acquire trustworthy data.
2. Prepare the data and train the local baseline.
3. Evaluate, approve, and track the model with MLflow.
4. Reproduce the environment with pinned dependencies, CI, and Docker.
5. Provision Azure ML and create versioned assets and components.
6. Run, govern, register, and deploy models.
7. Add safe releases, rollback, monitoring, retraining, and production CI/CD.

See [Project Phases and Checkpoints](docs/PROJECT_PHASES.md) for the granular
15-phase learning sequence.

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
`what-if`; deployment is intentionally pending. Phases 8 through 14 are
implemented and locally testable, including asset registration, a governed
pipeline, evidence-gated registration, online/batch deployment definitions,
release traffic controls, monitoring decisions, CI/CD, and runbooks. They are
not marked complete because their live Azure jobs, endpoint tests, monitoring,
and rollback exercise still require an authorized deployed environment. See the
[infrastructure guide](infra/README.md), the
[policy review](docs/PHASE7_POLICY_REVIEW.md), and the
[current progress table](docs/PROJECT_PHASES.md#current-progress).
