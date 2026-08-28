# Phase 1 Tutorial: Build the Local MLOps Lifecycle

> **Implementation status:** Complete. The dataset can be downloaded,
> prepared, trained, evaluated, approved, and tracked through one local MLflow
> lifecycle command.

## Outcome

By the end of this tutorial, the repository should run one complete local
workflow:

```text
raw data
  -> validation and deterministic split
  -> model training
  -> evaluation
  -> approval decision
  -> MLflow tracking
  -> MLflow model artifact and evaluation report
```

Do not use live Azure resources during this phase. The purpose is to make the
local logic reliable before Azure ML orchestrates it.

## What You Will Learn

- Why MLOps starts with reproducibility rather than deployment.
- How to make data, parameters, metrics, code, and artifacts traceable.
- How to separate preparation, training, evaluation, and orchestration.
- How to establish an explicit model-quality gate.
- How to test ML logic without depending on Azure.

## Prerequisites

- Python 3.10 or later.
- Git.
- A Python virtual environment.
- The repository dependencies installed.

From the repository root:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python -m pytest
```

The existing test should pass before you begin. Record unrelated baseline
failures instead of hiding them.

## Step 1: Define the ML Problem

Before changing code, add a short problem definition to the README or a
dedicated data document.

Document:

1. What one row represents.
2. Which column is the target.
3. Whether the problem is binary classification.
4. Which prediction is the positive class.
5. How the prediction would be used.
6. Which mistakes are most costly.
7. Which metric decides whether a model is acceptable.

For a churn-style example:

- One row represents one customer.
- The target indicates whether the customer churned.
- Recall measures how many actual churners are detected.
- Precision measures how often a churn warning is correct.
- ROC-AUC measures ranking quality independently of one threshold.
- A release may require minimum recall while preventing a major precision
  regression.

### Checkpoint

You should be able to explain why accuracy alone is insufficient for the
chosen problem.

## Step 2: Define Configuration and Reproducibility

Create a checked configuration file for local development. It should describe
behavior, not secrets.

Plan fields such as:

```yaml
data:
  input_path: data/raw/customers.csv
  target_column: churn
  test_size: 0.2

training:
  random_state: 42
  max_iter: 1000

evaluation:
  decision_threshold: 0.5
  minimum_f1: 0.75
  minimum_recall: 0.70

tracking:
  experiment_name: mlops-portfolio
```

Configuration must fail clearly when required fields are absent or invalid.
Do not silently replace invalid values with defaults.

Keep environment-specific values outside the file:

- MLflow tracking URI.
- Azure subscription and workspace details.
- Credentials and tokens.

### Why This Matters

If parameters exist only inside Python code, reproducing a prior run requires
knowing which source version was used. Checked configuration makes intended
runtime behavior visible and reviewable.

### Checkpoint

Given only a Git revision and the configuration file, another engineer should
know the intended seed, split, model parameters, and quality thresholds.

## Step 3: Add a Small Versioned Dataset

Choose a small public or synthetic dataset that can legally be committed, or
provide a deterministic download/generation script.

Use a structure similar to:

```text
data/
|-- raw/
|   `-- customers.csv
`-- README.md
```

The data documentation should include:

- Source and license.
- Retrieval or generation date.
- Schema.
- Target definition.
- Known limitations.
- Whether the file is committed or generated.

Never commit confidential, personal, licensed, or production data.

### Dataset Reference

For Phase 1, calculate and log a stable reference such as:

- File path.
- File size.
- SHA-256 checksum.
- Row and column counts.

Azure ML data asset name and version will replace or supplement this local
reference in a later phase.

### Checkpoint

Changing the dataset contents should produce a different logged checksum.

## Step 4: Separate Data Preparation

Create a preparation module responsible for:

1. Loading the input file.
2. Checking required columns.
3. Rejecting missing or invalid target values.
4. Separating features and target.
5. Creating a deterministic train/test split.
6. Writing prepared outputs.

The split must use:

- The configured random seed.
- Stratification for binary classification when appropriate.
- A fixed test proportion.

Do not perform the split independently inside training and evaluation. Both
stages must consume the same prepared outputs.

### Suggested Outputs

```text
artifacts/prepared/
|-- train.csv
|-- test.csv
`-- metadata.json
```

`metadata.json` should record the source checksum, schema, row counts, split
parameters, and creation time.

### Checkpoint

Running preparation twice against the same data and configuration should
produce equivalent train/test membership.

## Step 5: Turn Training into an Executable Stage

The current `src/train.py` exposes functions but cannot execute the command
declared in the Azure ML pipeline.

Add a command-line contract conceptually equivalent to:

```text
python -m src.train \
  --training-data <prepared-training-file> \
  --model-output <output-directory> \
  --config <configuration-file>
```

Training should:

1. Validate input paths.
2. Load prepared training data.
3. Build the scikit-learn pipeline.
4. Fit the model.
5. Save an MLflow model to the requested output directory.
6. Emit useful, non-sensitive progress information.

Keep the pure `train_model` function. The CLI should adapt files and
configuration to that function rather than placing all logic in one script.

### Why MLflow Model Format

An MLflow model directory records the model flavor and loading instructions.
This allows Azure ML to recognize and deploy the artifact more consistently
than an unexplained pickle file.

### Checkpoint

The command should create an artifact that can be loaded through MLflow and
used for predictions in a fresh Python process.

## Step 6: Expand Evaluation

Keep the existing metrics:

- Accuracy.
- Precision.
- Recall.
- F1.
- ROC-AUC.

Add:

- Confusion-matrix counts.
- The configured decision threshold.
- Threshold-specific precision, recall, and F1.
- Dataset row count.
- Model-approval result.

Evaluation should have a command-line contract similar to:

```text
python -m src.evaluate \
  --model-input <mlflow-model-directory> \
  --test-data <prepared-test-file> \
  --evaluation-output <output-directory> \
  --config <configuration-file>
```

Write a machine-readable report:

```json
{
  "metrics": {
    "accuracy": 0.0,
    "precision": 0.0,
    "recall": 0.0,
    "f1": 0.0,
    "roc_auc": 0.0
  },
  "thresholds": {
    "minimum_f1": 0.75,
    "minimum_recall": 0.70
  },
  "approved": false
}
```

The numbers above are structural examples, not recommended thresholds.
Choose thresholds based on the selected dataset and business objective.

### Checkpoint

A deliberately poor model or impossible threshold should produce
`"approved": false`.

## Step 7: Create One Local Orchestrator

Create one entry point that coordinates the stages without duplicating their
logic.

Conceptual command:

```text
python -m pipelines.run_local --config configs/local.yml
```

The orchestrator should:

1. Start a descriptive MLflow run.
2. Record the source Git revision.
3. Record the dataset path and checksum.
4. Log configuration and model parameters.
5. Run preparation.
6. Train and persist the model.
7. Evaluate the model.
8. Log all metrics and the evaluation report.
9. Log the MLflow model artifact.
10. Return a nonzero exit code when required stages fail.

Use run names that distinguish intent, for example:

- `baseline-logistic-regression`
- `tuning-candidate-<identifier>`
- `release-candidate-<identifier>`

Do not catch broad exceptions merely to mark a failed workflow as successful.
MLflow should preserve the failed run status.

### Source Revision

Log the current Git commit when available. If the worktree has modifications,
also log that it was dirty. A commit hash alone is not complete provenance
when uncommitted files changed the run.

### Checkpoint

The MLflow run should answer:

- Which code produced this model?
- Which data was used?
- Which parameters were used?
- Which metrics were observed?
- Where is the evaluation report?
- Where is the model artifact?
- Did the model meet the approval thresholds?

## Step 8: Run MLflow Locally

Start with the simplest tracking setup:

```powershell
$env:MLFLOW_TRACKING_URI = "file:./mlruns"
python -m pipelines.run_local --config configs/local.yml
mlflow ui --backend-store-uri ./mlruns
```

Then open the local MLflow UI and compare runs.

The file backend is appropriate for an individual learning project. If the
project later needs a shared local environment, Docker Compose can provide:

- An MLflow tracking server.
- PostgreSQL for run metadata.
- Object-compatible artifact storage.
- A trainer container.

Do not expand Compose merely for appearance. Introduce the services only when
you are ready to learn and maintain them.

### Checkpoint

At least two runs with different parameters should be visible and comparable
in the MLflow UI.

## Step 9: Establish the Registration Boundary

Do not register a model in Phase 1, because registration is an Azure-facing
operation planned for later phases. Instead, define the evidence that future
registration will require:

- An approved evaluation report.
- MLflow run ID.
- Model artifact URI.
- Dataset reference and checksum.
- Git revision.
- Environment and dependency information.
- Primary and secondary metrics.

Update the registration design so it will reject:

- Missing evaluation output.
- An evaluation with `approved: false`.
- Missing run or data provenance.
- A missing model artifact.

### Checkpoint

The local workflow should produce a complete release-candidate bundle even
though it does not yet register it in Azure.

## Step 10: Add Tests

Organize tests by purpose as the suite grows.

### Unit Tests

Test:

- Empty features.
- Feature/target length mismatch.
- Invalid binary probability output.
- Metric calculations.
- Threshold decision behavior.
- Configuration validation.
- Dataset checksum behavior.

### Reproducibility Test

Run preparation and training twice with the same inputs and seed. Verify:

- Identical train/test membership.
- Equivalent predictions.
- Equivalent evaluation metrics.

Exact serialized model bytes do not always need to match because metadata can
vary. Test meaningful deterministic behavior rather than an unreliable proxy.

### Artifact Test

Run the local lifecycle in a temporary directory and verify:

- Prepared data exists.
- Metadata exists.
- The MLflow model can be loaded.
- The evaluation report has the required schema.
- MLflow receives expected parameters and metrics.

### Failure Tests

Verify clear failures for:

- Missing data.
- Missing target column.
- Invalid configuration.
- One-class evaluation data where ROC-AUC is undefined.
- Missing model artifact.

### Checkpoint

All deterministic local tests must pass without Azure credentials or network
access.

## Step 11: Pin and Separate Dependencies

The project now defines exact runtime and development dependencies in
`pyproject.toml`; `requirements.txt` remains as the pinned runtime list used by
the Docker build.

Move toward:

- `pyproject.toml` for project metadata and direct dependencies.
- A lock or compiled requirements file for exact environments.
- Separate development tools from runtime dependencies.
- Explicit Python version support.

Record dependency versions in every MLflow run. Avoid upgrading all packages
while debugging an unrelated model change.

### Checkpoint

A fresh virtual environment should install the same resolved versions used by
CI.

## Step 12: Decide the Docker Compose Outcome

After the local lifecycle works, decide:

### Option A: Keep Compose

Choose this when you want a realistic shared local MLflow stack. Document:

- Service responsibilities.
- Persistent volumes.
- Ports.
- Startup and shutdown commands.
- Database migrations or initialization.
- Cleanup behavior.

### Option B: Remove Compose

Choose this when the file-backed MLflow store is sufficient. Retain the
Dockerfile and document:

```text
docker build
docker run
```

One container does not require Compose.

This project selected Option B. Local MLflow metadata uses SQLite, and a single
container does not justify a Compose configuration.

In either case, harden the Dockerfile by pinning its base, using a non-root
user, and giving it a working command.

## Recommended Work Sessions

### Session 1: Problem and Data

- Define the prediction problem.
- Select or generate the dataset.
- Document schema and license.
- Define configuration and thresholds.

### Session 2: Preparation and Training

- Implement validated data preparation.
- Add deterministic splitting.
- Add the training CLI.
- Save an MLflow model.

### Session 3: Evaluation and Gate

- Add threshold-specific evaluation.
- Write the evaluation report.
- Implement the approval decision.

### Session 4: Tracking and Orchestration

- Add the local orchestrator.
- Log complete lineage.
- Inspect and compare runs in MLflow.

### Session 5: Tests and Reproducibility

- Add unit and failure tests.
- Add lifecycle artifact tests.
- Pin dependencies.
- Document the local command.

### Session 6: Container Decision

- Make the Docker image execute the lifecycle.
- Harden the image.
- Expand or remove Docker Compose based on an actual local need.

## Phase 1 Definition of Done

Phase 1 is complete when:

1. One documented command runs the complete local lifecycle.
2. Data preparation and splitting are deterministic.
3. Training writes a loadable MLflow model.
4. Evaluation writes a structured report with multiple metrics.
5. A configured quality gate marks the candidate approved or rejected.
6. MLflow records code, data, parameters, dependencies, metrics, report, and
   model artifact.
7. Failures return nonzero status and remain visible.
8. Tests pass without Azure credentials.
9. Dependencies are reproducible.
10. Docker has a clear, working purpose and Compose has been justified or
    removed.

The model lifecycle portion of this definition is complete. Dependency
pinning, Docker hardening, and the final Compose decision are tracked
separately as Phase 6 in
[Project Phases and Checkpoints](PROJECT_PHASES.md).

## What Comes Next

After every definition-of-done item passes, proceed to Phase 2 of the
[AI-300 MLOps roadmap](AI300_MLOPS_ROADMAP.md): convert preparation, training,
and evaluation into reusable Azure ML components and compose them into a
submittable pipeline.
