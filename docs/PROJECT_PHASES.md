# Project Phases and Checkpoints

## How to Use This Document

This is the main project guide. Work through one phase at a time.

For every phase:

1. Learn what the phase is for.
2. Complete only the listed work.
3. Inspect the files and outputs yourself.
4. Answer the understanding checkpoints.
5. Run the verification checkpoints.
6. Do not begin the next phase until every required checkpoint passes.

The project is split into small phases so you can understand what is happening
instead of receiving a finished system that you cannot explain.

## Status Key

- `[x]` Complete and verified before the documentation hierarchy tweak.
- `[~]` Implemented offline but still requires one or more live Azure checks.
- `[ ]` Not started.

## Current Progress

| Phase | Name                                     | Status  |
| ----- | ---------------------------------------- | ------- |
| 0     | Understand the project                   | `[x]` |
| 1     | Choose and acquire the dataset           | `[x]` |
| 2     | Prepare and split the data               | `[x]` |
| 3 | Train the first model | `[x]` |
| 4 | Evaluate and approve the model | `[x]` |
| 5 | Track the complete run with MLflow | `[x]` |
| 6 | Make the local environment reproducible | `[x]` |
| 7     | Provision Azure ML infrastructure        | `[~]` |
| 8     | Create Azure ML assets and components    | `[~]` |
| 9     | Run the Azure ML training pipeline       | `[~]` |
| 10    | Register and govern models               | `[~]` |
| 11    | Deploy online and batch endpoints        | `[~]` |
| 12    | Release safely and support rollback      | `[~]` |
| 13    | Monitor, alert, and retrain              | `[~]` |
| 14    | Complete production CI/CD and operations | `[~]` |

Phases 0 through 6 were complete before the documentation hierarchy tweak. The complete local lifecycle is reproducible
in the pinned Python environment and the non-root Docker image. Phase 7 is in
progress: its policy-aware Bicep builds successfully, passes Azure validation,
and has a reviewed development `what-if`. Deployment is still pending. Phases
8 through 14 now have offline implementation, contracts, tests, workflows, and
runbooks, but remain `[~]` until their live Azure checkpoints pass. See the
[hierarchical implementation record](IMPLEMENTATION_RECORD.md) for what was
done, why, evidence, dependencies, and remaining live gates.

---

## Phase 0: Understand the Project

### Goal

Understand the business problem and the complete model lifecycle before
touching implementation.

### Plain-English Explanation

We want to build a model that estimates whether a bank client will subscribe
to a term deposit. The model itself is only one part of the project. MLOps is
the system that makes the model repeatable, testable, deployable, observable,
and replaceable.

### Files to Read

- `README.md`
- `docs/ML_PROBLEM.md`
- `docs/diagrams/mlops-learning-flow.drawio`
- `docs/AI300_MLOPS_ROADMAP.md`

### Understanding Checkpoints

- [ ] I can explain what the model predicts.
- [ ] I know that `yes` is the positive class.
- [ ] I can explain the difference between training and testing.
- [ ] I can explain why a model artifact is not the same as a deployed model.
- [ ] I can explain why MLOps includes data, code, configuration, deployment,
  monitoring, and retraining.

### Verification Checkpoint

Open `docs/diagrams/mlops-learning-flow.drawio` and trace the flow from the UCI
website to Azure ML.

### Phase Gate

Do not continue until you can explain the diagram without reading its labels
word for word.

---

## Phase 1: Choose and Acquire the Dataset

### Goal

Obtain one trustworthy copy of the public dataset and prove exactly where it
came from.

### What Happens

The download script retrieves the official UCI archive, verifies checksums,
extracts the selected CSV, checks its dimensions, and writes provenance
metadata.

### Important Files

- `scripts/download_bank_marketing.py`
- `data/README.md`
- `data/raw/bank-additional-full.csv`
- `data/raw/bank-additional-full.metadata.json`

The files under `data/raw/` are local artifacts and are intentionally ignored
by Git.

### Command

```powershell
python -m scripts.download_bank_marketing
```

### Understanding Checkpoints

- [X] I know where the original CSV is stored.
- [X] I know that one row represents one campaign observation.
- [X] I know that `y` is the target column.
- [X] I can explain what a SHA-256 checksum proves.
- [X] I understand why raw downloaded data is not edited manually.
- [X] I know where the dataset source, DOI, license, and attribution are
  documented.

### Verification Checkpoints

- [X] The official archive checksum is verified.
- [X] The CSV checksum is verified.
- [X] The dataset contains 41,188 rows and 21 columns.
- [X] Provenance metadata is generated.
- [X] `data/raw/` is ignored by Git.

### Phase Gate

The phase passes when the dataset can be deleted and recreated using only the
documented command.

---

## Phase 2: Prepare and Split the Data

### Goal

Create a repeatable training set and an untouched test set.

### Plain-English Explanation

The model learns from `train.csv`. It must not learn from `test.csv`.
`test.csv` is held back so that later evaluation measures performance on data
the model did not see during training.

### Important Files

- `configs/local.json`
- `src/prepare_data.py`
- `artifacts/prepared/train.csv`
- `artifacts/prepared/test.csv`
- `artifacts/prepared/metadata.json`

The files under `artifacts/` are generated outputs and are ignored by Git.

### Command

```powershell
python -m src.prepare_data --config configs/local.json
```

### What the Stage Must Do

- Validate the expected columns.
- Validate the two target values: `yes` and `no`.
- Remove the prohibited `duration` feature.
- Create a stratified 80/20 split.
- Use random seed 42.
- Record data checksums, row counts, class counts, and split settings.

### Understanding Checkpoints

- [ ] I can explain why the dataset is split.
- [ ] I can explain why the test set must remain untouched during training.
- [ ] I can explain what a random seed does.
- [ ] I can explain why stratification keeps the class proportions similar.
- [ ] I can explain why `duration` would leak information from the future.
- [ ] I know that configuration controls the split instead of hidden values in
  code.

### Verification Checkpoints

- [X] Training data contains 32,950 rows.
- [X] Test data contains 8,238 rows.
- [X] Both files contain 20 columns including the target.
- [X] Neither file contains `duration`.
- [X] The same data and configuration create the same split.
- [X] Split metadata contains checksums and class counts.

### Phase Gate

The phase passes when repeated preparation produces equivalent training and
test membership and all preparation tests pass.

---

## Phase 3: Train the First Model

### Goal

Teach a logistic-regression model using only `train.csv` and save the trained
pipeline as a reusable MLflow model artifact.

### Plain-English Explanation

The data contains both numbers and words. A machine-learning algorithm needs
those columns transformed consistently:

- Numeric values are filled when missing and scaled.
- Categorical values are filled when missing and one-hot encoded.
- Logistic regression learns how the transformed inputs relate to `y`.

All preprocessing must be saved inside the same model pipeline. Otherwise,
future predictions may be transformed differently from the training data.

### Important Files

- `src/train.py`
- `configs/local.json`
- `artifacts/prepared/train.csv`
- `artifacts/model/baseline/`
- `tests/test_train.py`

### Intended Command

```powershell
python -m src.train --config configs/local.json
```

### Work Checklist

- [X] Read the prepared training CSV.
- [X] Separate features from target `y`.
- [X] Identify numeric and categorical columns.
- [X] Build numeric preprocessing.
- [X] Build categorical preprocessing.
- [X] Train logistic regression.
- [X] Save an MLflow model and training metadata.
- [X] Test unseen categorical values.
- [x] Re-run training after the final safe-serialization adjustment.
- [x] Re-run the training test suite after that adjustment.
- [x] Load the final saved model in a fresh process and make a prediction.

### Understanding Checkpoints

- [ ] I can explain what a feature is.
- [ ] I can explain the difference between numeric and categorical features.
- [ ] I can explain one-hot encoding in simple terms.
- [ ] I can explain why scaling is applied to numeric columns.
- [ ] I can explain why preprocessing and the classifier are saved together.
- [ ] I know that training uses `train.csv`, not `test.csv`.
- [ ] I can explain what a saved model artifact contains.

### Verification Checkpoints

- [x] Training completes without an error.
- [x] `artifacts/model/baseline/MLmodel` exists.
- [x] The model can be loaded through MLflow.
- [x] The loaded model accepts a valid row and returns `yes` or `no`.
- [x] The saved metadata records the training-data checksum and parameters.
- [x] The Step 5 training test suite passes.

### Phase Gate

Do not begin evaluation until the final model artifact can be loaded in a
fresh Python process and produce a prediction.

---

## Phase 4: Evaluate and Approve the Model

### Goal

Measure the trained model once against untouched `test.csv` and decide whether
it meets declared quality thresholds.

### Important Files to Create or Complete

- `src/evaluate.py`
- `artifacts/evaluation/metrics.json`
- `artifacts/evaluation/confusion_matrix.json`
- Evaluation tests.

### Metrics

- Accuracy.
- Precision.
- Recall.
- F1.
- ROC-AUC.
- True positives, false positives, true negatives, and false negatives.
- Decision threshold.

### Work Checklist

- [x] Load the saved MLflow model.
- [x] Load only `test.csv`.
- [x] Generate probabilities and predictions.
- [x] Calculate all required metrics.
- [x] Compare metrics with `configs/local.json`.
- [x] Write a machine-readable evaluation report.
- [x] Mark the model approved or rejected.
- [x] Test both passing and failing approval decisions.

### Understanding Checkpoints

- [ ] I can explain why accuracy is misleading for imbalanced data.
- [ ] I can explain precision.
- [ ] I can explain recall.
- [ ] I can explain the precision/recall tradeoff.
- [ ] I can explain why ROC-AUC does not depend on only one threshold.
- [ ] I understand that a failed model should not be registered.

### Verification Checkpoints

- [x] Evaluation never fits or changes the model.
- [x] Evaluation uses only the untouched test set.
- [x] The report contains all metrics and thresholds.
- [x] A failing threshold produces `approved: false` in tests.
- [x] Evaluation tests pass.

### Phase Gate

The phase passes when the same model and test data produce the same report and
the approval decision is explicit.

---

## Phase 5: Track the Complete Run with MLflow

### Goal

Record the whole local experiment so another engineer can identify exactly how
the model was produced.

### What MLflow Must Record

- Run name and run ID.
- Git commit and dirty-worktree status.
- Dataset path and checksum.
- Split metadata.
- Model parameters.
- Dependency versions.
- Evaluation metrics.
- Approval result.
- Evaluation report.
- Model artifact.

### Work Checklist

- [x] Create one local orchestration command.
- [x] Start one descriptive MLflow run.
- [x] Run preparation, training, and evaluation in order.
- [x] Log complete lineage and artifacts.
- [x] Preserve failed run status through the MLflow run context.
- [x] Compare at least two independent runs.

### Understanding Checkpoints

- [ ] I can explain the difference between an experiment, run, parameter,
  metric, tag, and artifact.
- [ ] I can find the model artifact for a run.
- [ ] I can identify the data checksum used by a run.
- [ ] I can compare two runs and explain which is better and why.

### Verification Checkpoints

- [x] One command runs the complete local lifecycle.
- [x] MLflow stores complete run information in `mlflow.db`.
- [x] Exceptions propagate so failed stages leave failed MLflow runs.
- [x] Repeated runs remain independently traceable.

### Phase Gate

The local lifecycle is complete only when a run answers: which code, which
data, which configuration, which metrics, and which model?

---

## Phase 6: Make the Local Environment Reproducible

### Goal

Ensure another computer and CI can recreate the same runtime.

### Work Checklist

- [x] Move project metadata and dependencies to `pyproject.toml`.
- [x] Pin resolved dependency versions.
- [x] Separate runtime and development dependencies.
- [x] Pin the Python version used by CI.
- [x] Harden the Dockerfile.
- [x] Run the container as a non-root user.
- [x] Make the container run a real project command.
- [x] Either expand Docker Compose into a useful local MLflow stack or remove
  it.
- [x] Add formatting, linting, type checking, and tests to CI.

### Understanding Checkpoints

- [ ] I can explain why unpinned dependencies hurt reproducibility.
- [ ] I can explain what Docker contributes.
- [ ] I can explain why Docker Compose is not the Azure production
  deployment.
- [ ] I can explain why production containers should not run as root.

### Verification Checkpoints

- [x] The project builds and installs from `pyproject.toml`.
- [x] All 14 tests pass using the pinned environment.
- [x] The Docker image builds.
- [x] The non-root container runs the documented lifecycle.
- [x] CI defines formatting, linting, type checking, tests, Azure SDK import,
      image build, and non-root runtime checks.

### Phase Gate

Do not move to Azure until the local lifecycle and environment are both
repeatable.

---

## Phase 7: Provision Azure ML Infrastructure

### Goal

Create the required Azure resources from source-controlled infrastructure
code.

### Resources

- Azure ML workspace.
- Storage account.
- Key Vault.
- Monitoring integration.
- CPU compute cluster.
- Managed identities.
- Least-privilege RBAC.
- Optional registry when justified.
- Private networking required by the selected subscription's policies.

### Work Checklist

- [x] Add Bicep modules.
- [x] Add development, staging, and production parameter files.
- [x] Validate Bicep.
- [x] Review `what-if` output.
- [ ] Deploy a development environment.
- [ ] Configure GitHub OIDC.
- [x] Confirm no secrets or subscription details are committed.
- [x] Document cost controls and cleanup.

### Understanding Checkpoints

- [ ] I can explain what the Azure ML workspace contains.
- [ ] I can explain the difference between compute, storage, and registry.
- [ ] I can explain managed identity and RBAC.
- [ ] I can explain why OIDC is preferred to stored client secrets.
- [ ] I know which resources cost money while idle.

### Verification Checkpoints

- [ ] Infrastructure can be recreated from Bicep.
- [ ] Authentication works without committed secrets.
- [x] Compute can scale down to zero.
- [ ] Cleanup instructions work.

### Phase Gate

The phase passes when a clean Azure development environment can be recreated
from the repository.

---

## Phase 8: Create Azure ML Assets and Components

### Goal

Turn local files and stages into versioned Azure ML assets.

### Assets

- Data asset.
- Environment.
- Preparation component.
- Training component.
- Evaluation component.
- Registration component.

### Work Checklist

- [ ] Register the dataset as a versioned data asset.
- [ ] Create a pinned Azure ML environment.
- [ ] Give every component explicit typed inputs and outputs.
- [ ] Use small component-specific code directories.
- [ ] Version components.
- [ ] Test component construction without live Azure access.

### Understanding Checkpoints

- [ ] I can explain the difference between a local file and a data asset.
- [ ] I can explain why environments and components are versioned.
- [ ] I can identify every input and output of each component.
- [ ] I can explain how versioning supports rollback and lineage.

### Verification Checkpoints

- [ ] All required assets appear in Azure ML.
- [ ] Component definitions build locally.
- [ ] No component relies on hidden local paths.
- [ ] Evaluation evidence is a required input to registration.

### Phase Gate

The phase passes when each lifecycle stage is reusable and independently
versioned.

---

## Phase 9: Run the Azure ML Training Pipeline

### Goal

Run preparation, training, evaluation, and registration as one Azure ML
pipeline.

### Work Checklist

- [ ] Compose the versioned components.
- [ ] Submit the pipeline through `MLClient`.
- [ ] Configure compute and inputs.
- [ ] Track the run with MLflow.
- [ ] Compare the cloud run with the local baseline.
- [ ] Add hyperparameter sweep training.
- [ ] Add an AutoML benchmark.
- [ ] Preserve complete lineage.

### Understanding Checkpoints

- [ ] I can explain orchestration.
- [ ] I can explain the difference between a pipeline, component, and job.
- [ ] I can explain baseline, tuning, and release-candidate runs.
- [ ] I can explain why AutoML is a benchmark rather than magic.

### Verification Checkpoints

- [ ] The cloud pipeline completes.
- [ ] Every stage has explicit inputs and outputs.
- [ ] The winning run is selected by declared metrics.
- [ ] The Azure run retains code, data, environment, and parameter lineage.

### Phase Gate

The phase passes when a pipeline run is reproducible from a versioned data
asset and checked configuration.

---

## Phase 10: Register and Govern Models

### Goal

Allow only evaluated, traceable models into the registry.

### Work Checklist

- [ ] Require an approved evaluation report.
- [ ] Require MLflow run and model artifact references.
- [ ] Require data, code, environment, and parameter provenance.
- [ ] Compare candidates with the current approved model.
- [ ] Add Responsible AI analysis appropriate to the use case.
- [ ] Apply lifecycle tags such as candidate, staging, approved, and archived.
- [ ] Document rejection and archival.

### Understanding Checkpoints

- [ ] I can explain why training success is not approval.
- [ ] I can explain model versioning.
- [ ] I can explain what provenance is.
- [ ] I can explain why a model may be archived rather than deleted.

### Verification Checkpoints

- [ ] Missing evidence blocks registration.
- [ ] Failed thresholds block registration.
- [ ] Every registered model links to its run and evaluation.
- [ ] Approval decisions are auditable.

### Phase Gate

No model may deploy unless its registry record proves that it passed the
defined gate.

---

## Phase 11: Deploy Online and Batch Endpoints

### Goal

Serve approved models through both major Azure ML inference patterns.

### Work Checklist

- [ ] Create a managed online endpoint.
- [ ] Create a batch endpoint.
- [ ] Add input schema validation.
- [ ] Use managed identity.
- [ ] Add smoke tests.
- [ ] Add contract tests.
- [ ] Add endpoint integration tests.
- [ ] Separate staging and production configuration.

### Understanding Checkpoints

- [ ] I can explain when to use online inference.
- [ ] I can explain when to use batch inference.
- [ ] I can explain endpoint versus deployment.
- [ ] I can explain autoscaling and managed identity.

### Verification Checkpoints

- [ ] Online requests return the expected response shape.
- [ ] Batch jobs write expected outputs.
- [ ] Invalid input fails clearly.
- [ ] Deployments are associated with approved model versions.

### Phase Gate

The phase passes when both endpoint types are deployed through repeatable
automation and tested.

---

## Phase 12: Release Safely and Support Rollback

### Goal

Release a new model without immediately replacing the known-good model.

### Work Checklist

- [ ] Deploy a candidate separately from production.
- [ ] Route a small traffic percentage to the candidate.
- [ ] Define an observation window.
- [ ] Compare health and quality signals.
- [ ] Require production approval where appropriate.
- [ ] Promote traffic gradually.
- [ ] Automate rollback to the previous deployment.
- [ ] Test rollback.

### Understanding Checkpoints

- [ ] I can explain canary deployment.
- [ ] I can explain blue-green deployment.
- [ ] I can explain why model version alone is insufficient for rollback.
- [ ] I know which signals trigger rollback.

### Verification Checkpoints

- [ ] A failed candidate cannot destroy the previous deployment.
- [ ] Traffic can return to the known-good version.
- [ ] Release and rollback events are auditable.

### Phase Gate

The phase passes only after rollback is tested, not merely documented.

---

## Phase 13: Monitor, Alert, and Retrain

### Goal

Detect when the service or model stops behaving acceptably.

### Signals

- Availability and errors.
- Latency and throughput.
- Resource usage and cost.
- Input data quality.
- Data drift.
- Prediction distribution.
- Model quality when labels become available.

### Work Checklist

- [ ] Create operational dashboards.
- [ ] Configure alerts.
- [ ] Assign alert ownership.
- [ ] Detect data drift.
- [ ] Measure prediction quality when ground truth arrives.
- [ ] Define scheduled and threshold-triggered retraining.
- [ ] Send retrained models through the same evaluation and release gates.

### Understanding Checkpoints

- [ ] I can explain data drift and concept drift.
- [ ] I can distinguish service health from model quality.
- [ ] I can explain why predictions alone do not prove correctness.
- [ ] I can explain why retraining must not bypass governance.

### Verification Checkpoints

- [ ] Simulated failures trigger alerts.
- [ ] Drift calculations produce visible results.
- [ ] Retraining creates a new traceable candidate.
- [ ] The candidate still requires approval and safe release.

### Phase Gate

The phase passes when the team can detect, investigate, and respond to both
service and model degradation.

---

## Phase 14: Complete Production CI/CD and Operations

### Goal

Make the system maintainable by a team without undocumented manual steps.

### Work Checklist

- [ ] Pull-request validation workflow.
- [ ] Bicep validation and `what-if`.
- [ ] Infrastructure deployment workflow.
- [ ] Training workflow.
- [ ] Staging deployment and endpoint tests.
- [ ] Production approval.
- [ ] Canary release and promotion.
- [ ] Security and dependency scanning.
- [ ] Architecture documentation.
- [ ] Model-governance documentation.
- [ ] Incident and rollback runbooks.
- [ ] Cost and cleanup documentation.
- [ ] Retraining operations documentation.

### Understanding Checkpoints

- [ ] I can describe the complete path from Git commit to production.
- [ ] I can identify every human and automated approval.
- [ ] I know how to investigate a failed training or deployment run.
- [ ] I know how to roll back.
- [ ] I know how to clean up resources and control cost.

### Verification Checkpoints

- [ ] Routine delivery requires no hidden local steps.
- [ ] All environment changes are reviewable.
- [ ] Model releases are auditable.
- [ ] Another engineer can provision, train, deploy, monitor, and recover the
  system using only repository documentation.

### Final Gate

The MLOps project is complete when the entire lifecycle can be demonstrated,
explained, reproduced, monitored, and safely reversed.

---

## AI-300 Boundary

Completing these phases provides strong coverage of the traditional MLOps
objectives in AI-300. The full exam also includes Microsoft Foundry and
GenAIOps topics such as foundation-model deployment, prompt versioning, agent
evaluation, safety, observability, RAG optimization, and fine-tuning.

Those topics should become a separate project phase plan after this MLOps
lifecycle is complete and understood.
