---
title: Hierarchical Implementation Record
description: Traceable implementation decisions, evidence, and remaining live gates.
---

## Purpose and Status Rules

This record applies the required project hierarchy:

1. **Major project stage** - a lifecycle outcome.
2. **Overall phase** - a coherent group of work within that stage.
3. **Granular task** - an actionable, verifiable implementation item.

Every row records what was done, why it exists, its evidence, and its current
status. The detailed commands and learning checkpoints remain in
[`PROJECT_PHASES.md`](PROJECT_PHASES.md).

Status meanings:

- **Done before tweak** - implemented and verified before the hierarchical
  documentation requirement was introduced.
- **Offline complete** - implementation and local contracts exist, but a live
  Azure operation is still required.
- **Development live complete** - the development environment operation has
  succeeded with durable Azure or GitHub evidence; later environments or
  lifecycle exercises may still be pending.
- **Live pending** - cannot be truthfully completed without an authorized Azure
  environment, protected GitHub environments, or production observations.

## Major Stage A: Reproducible Local Model Lifecycle

**What:** Acquires verified source data, prepares it deterministically, trains
and evaluates a model, records lineage, and packages a reproducible runtime.

**Why:** Cloud orchestration cannot repair non-deterministic or untestable
model-development logic. Establishing a reliable local boundary makes later
Azure jobs easier to diagnose and keeps unit tests independent of cloud
credentials.

**Inputs:** UCI Bank Marketing archive, `configs/local.json`, Python 3.11, and
the checked dependency versions.

**Outputs:** Prepared CSV files, an MLflow model, evaluation evidence, an MLflow
run, a release-candidate bundle, and a non-root Docker image.

### Overall Phase 0: Understand the Project

| Granular task                 | Status            | What was done and why                                                                                                                         | Evidence and validation                        |
| ----------------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Define the business objective | Done before tweak | Defined pre-call term-deposit propensity as a binary probability problem so model behavior is tied to a legitimate decision point.            | `docs/ML_PROBLEM.md`                         |
| Define model-use boundaries   | Done before tweak | Prohibited automatic customer treatment and positioned the score as decision support to reduce misuse risk.                                   | `docs/ML_PROBLEM.md`                         |
| Define evaluation criteria    | Done before tweak | Selected precision, recall, F1, ROC-AUC, confusion counts, and configured thresholds because accuracy alone hides minority-class performance. | `docs/ML_PROBLEM.md`, `configs/local.json` |

### Overall Phase 1: Acquire Trusted Data

| Granular task               | Status            | What was done and why                                                                                                              | Evidence and validation                |
| --------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------- |
| Download the official asset | Done before tweak | Added a deterministic UCI download command so the raw file is reproducible rather than manually copied.                            | `scripts/download_bank_marketing.py` |
| Verify integrity            | Done before tweak | Verified the outer archive, nested archive, and CSV SHA-256 values to detect replacement or corruption.                            | `data/README.md`, download tests     |
| Record provenance           | Done before tweak | Wrote source, DOI, retrieval time, checksum, shape, target, and exclusion metadata so each downstream run can identify its origin. | Generated`data/raw/*.metadata.json`  |

### Overall Phase 2: Prepare and Split Data

| Granular task                | Status            | What was done and why                                                                                                        | Evidence and validation                                 |
| ---------------------------- | ----------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- |
| Validate schema and target   | Done before tweak | Rejects empty data, missing columns, missing targets, and unexpected labels before training can create misleading artifacts. | `src/prepare_data.py`, `tests/test_prepare_data.py` |
| Remove leakage               | Done before tweak | Requires exclusion of`duration` because it is unavailable at the intended prediction time.                                 | Preparation configuration and tests                     |
| Create deterministic holdout | Done before tweak | Uses a seeded, stratified 80/20 split so comparisons use stable membership and preserve class balance.                       | Prepared metadata and reproducibility test              |
| Support cloud-bound paths    | Offline complete  | Added explicit input and output overrides so the same stage can consume Azure ML data inputs without hidden local paths.     | `src/prepare_data.py` CLI contract                    |

### Overall Phase 3: Train the Baseline

| Granular task                     | Status            | What was done and why                                                                                                                         | Evidence and validation                   |
| --------------------------------- | ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------- |
| Build mixed-feature preprocessing | Done before tweak | Imputes and scales numeric columns and safely one-hot encodes categorical columns so training and inference transformations remain identical. | `src/train.py`, training tests          |
| Train deterministically           | Done before tweak | Uses checked logistic-regression parameters and seed to establish an explainable baseline.                                                    | `configs/local.json`, training metadata |
| Package an MLflow model           | Done before tweak | Saves preprocessing and classifier together in MLflow format for portable loading and Azure ML compatibility.                                 | Generated`MLmodel`, artifact tests      |
| Accept component folder input     | Offline complete  | Resolves`train.csv` from a prepared-data folder so Azure ML can pass one explicit stage output.                                             | `src/train.py`                          |

### Overall Phase 4: Evaluate and Approve

| Granular task                 | Status            | What was done and why                                                                                             | Evidence and validation                 |
| ----------------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------- | --------------------------------------- |
| Evaluate untouched data       | Done before tweak | Loads the persisted model and scores only the test split, preventing evaluation-time fitting.                     | `src/evaluate.py`                     |
| Calculate decision metrics    | Done before tweak | Reports threshold-specific metrics, ROC-AUC, and confusion counts to expose campaign efficiency and coverage.     | Evaluation report and tests             |
| Apply a quality gate          | Done before tweak | Produces an explicit approved/rejected result from checked thresholds so downstream registration can fail closed. | `approval_decision`, evaluation tests |
| Accept component folder input | Offline complete  | Resolves`test.csv` from the preparation output folder for explicit Azure ML dependency wiring.                  | `src/evaluate.py`                     |

### Overall Phase 5: Track the Complete Run

| Granular task         | Status            | What was done and why                                                                                                                                                                                       | Evidence and validation                                   |
| --------------------- | ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------- |
| Orchestrate one run   | Done before tweak | Runs preparation, training, and evaluation in one MLflow context so failures and artifacts share one run identity.                                                                                          | `pipelines/run_local.py`                                |
| Log lineage           | Done before tweak | Records source revision, dirty state, data checksums, parameters, dependency versions, metrics, configuration, and artifacts.                                                                               | Local MLflow database                                     |
| Emit release evidence | Offline complete  | Added`release_candidate.json` with approval, metrics, run ID, artifact URI, data reference, source revision, dependencies, and parameters. This creates the registration boundary required by governance. | `pipelines/run_local.py`, generated evaluation artifact |

### Overall Phase 6: Reproduce the Runtime

| Granular task         | Status            | What was done and why                                                                       | Evidence and validation                  |
| --------------------- | ----------------- | ------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Pin dependencies      | Done before tweak | Pins runtime and development dependencies to prevent unnoticed environment drift.           | `pyproject.toml`, `requirements.txt` |
| Enforce local quality | Done before tweak | Runs formatting, linting, typing, tests, and Azure SDK import checks on changes.            | `.github/workflows/ci.yml`             |
| Harden the container  | Done before tweak | Uses a pinned Python base, a narrow build context, pinned packages, and a non-root runtime. | `docker/Dockerfile`, `.dockerignore` |

## Major Stage B: Secure Azure Foundation

**What:** Defines the private, policy-aware resources and federated identity
needed by Azure ML.

**Why:** Repeatable infrastructure and least-privilege identity are
prerequisites for traceable jobs and safe automation.

### Overall Phase 7: Provision Azure ML Infrastructure

| Granular task                  | Status                    | What was done and why                                                                                                                                                                                                                                                                                                | Evidence and validation                                                                                                                                                                         |
| ------------------------------ | ------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Encode governed infrastructure | Done before tweak         | Added subscription-scoped Bicep for workspace, storage, Key Vault, monitoring, private networking, NAT, compute, identities, and RBAC.                                                                                                                                                                               | `infra/main.bicep`, `infra/modules/`                                                                                                                                                        |
| Separate environments          | Done before tweak         | Added development, staging, and production parameter files so changes remain reviewable and isolated.                                                                                                                                                                                                                | `infra/environments/`                                                                                                                                                                         |
| Prepare approved development artifacts | Offline complete | Added a local PowerShell bundle command that compiles both subscription bootstrap and resource-group update templates, preserving environment parameters and OIDC inputs. Reused existing Bicep instead of introducing a second infrastructure recipe. No resources were provisioned by this preparation step. | [Preparation command](../scripts/prepare_deployment.ps1), [offline contracts](../tests/test_infrastructure_artifacts.py), [usage and dependencies](../infra/README.md), [current plan](../.azure/deployment-plan.md). On 2026-10-18: three offline tests, Ruff, mypy, Bicep compilation, and generated-resource assertions passed. |
| Apply cost controls            | Done before tweak         | Uses zero-minimum compute, bounded maximum nodes, capped logs, and no idle Premium registry.                                                                                                                                                                                                                         | `infra/README.md`                                                                                                                                                                             |
| Bootstrap OIDC                 | Development live complete | Created the`dev`, `staging`, and `production` GitHub environments, protected staging and production with required review, deployed the development federated identity, and verified secretless `azure/login`. Post-bootstrap infrastructure operations use resource-group scope to preserve least privilege. | `infra/resource-group.bicep`, `.github/workflows/infrastructure.yml`, [successful OIDC validation run](https://github.com/oratilemeletse/end-to-end-mlops-pipeline/actions/runs/33174763262) |
| Deploy development             | Development live complete | Deployed the private development platform after validation and`what-if`. The deployment created the workspace, zero-minimum compute, storage, Key Vault, monitoring, private endpoints, NAT, identities, and RBAC.                                                                                                 | Azure subscription deployment`phase7-dev`; resource group `azrg4vd3mqhtingnw`                                                                                                               |
| Verify cleanup                 | Live pending              | Requires deleting the deployed development resource group and observing protected Key Vault retention behavior.                                                                                                                                                                                                      | Azure activity/deployment records                                                                                                                                                               |

## Major Stage C: Versioned Assets and Governed Training

**What:** Registers immutable assets and runs preparation, training,
evaluation, and registration as one dependency graph.

**Why:** Explicit assets and stage boundaries preserve lineage, independent
reuse, and fail-closed registration.

### Overall Phase 8: Create Azure ML Assets and Components

| Granular task                        | Status           | What was done and why                                                                                                                                                          | Evidence and validation                                   |
| ------------------------------------ | ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | --------------------------------------------------------- |
| Define a pinned environment          | Offline complete | Added a Python 3.11 conda environment with exact runtime package versions so cloud jobs use the same declared stack.                                                           | `components/environment/conda.yml`                      |
| Register data and environment assets | Offline complete | Added an idempotent SDK entry point with explicit names and versions. Workspace identifiers come from environment variables and authentication uses`DefaultAzureCredential`. | `pipelines/register_assets.py`, `src/azure_config.py` |
| Define component contracts           | Offline complete | Preparation, training, evaluation, and registration have typed inputs/outputs and verb-led component names.`.amlignore` keeps uploads focused.                               | `pipelines/azureml_pipeline.py`, `.amlignore`         |
| Verify assets in Azure ML            | Live pending     | Requires running registration against the deployed development workspace.                                                                                                      | Azure ML asset names and versions                         |

### Overall Phase 9: Run the Azure ML Training Pipeline

| Granular task                      | Status           | What was done and why                                                                                                                                      | Evidence and validation                  |
| ---------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------- |
| Compose lifecycle stages           | Offline complete | Wires prepared data into training and evaluation, then requires both the model and evaluation output for registration.                                     | `pipelines/azureml_pipeline.py`        |
| Submit through`MLClient`         | Offline complete | Added an environment-driven submission command that records source revision and emits the job and Studio references.                                       | `pipelines/submit_pipeline.py`         |
| Track a baseline release candidate | Offline complete | Uses a descriptive experiment name and immutable data/environment references supplied by the caller.                                                       | Submission CLI                           |
| Execute and compare cloud run      | Live pending     | Requires registered assets, compute, and the deployed workspace. The resulting metrics must be compared with the local baseline.                           | Azure ML job and MLflow run              |
| Run sweep and AutoML benchmark     | Live pending     | These consume Azure compute and should start only after the baseline cloud pipeline is verified. Selection criteria remain the configured quality metrics. | Future Azure ML sweep and AutoML job IDs |

## Major Stage D: Governance, Deployment, and Safe Release

**What:** Prevents unqualified registration, serves approved models through
online and batch endpoints, and changes production traffic reversibly.

**Why:** A trained artifact is not automatically safe to register or deploy.
Evidence, environment separation, and a known-good deployment are required.

### Overall Phase 10: Register and Govern Models

| Granular task                       | Status           | What was done and why                                                                                                                               | Evidence and validation                       |
| ----------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------- |
| Validate evidence                   | Offline complete | Rejects invalid JSON, failed approval, missing metrics, missing provenance, empty fields, and missing artifacts before constructing a cloud client. | `src/register_model.py`, registration tests |
| Attach audit metadata               | Offline complete | Stores lifecycle stage, MLflow run, source revision, data reference, metrics, parameters, dependencies, and artifact URI on the model asset.        | `build_model_asset`                         |
| Enforce the pipeline gate           | Offline complete | Registration consumes evaluation output and model output; a failed report raises an error and fails the component.                                  | `components/register_model/run.py`          |
| Register and review a model version | Live pending     | Requires a completed cloud job and authorization for model asset creation.                                                                          | Azure ML model version and attached metadata  |
| Complete Responsible AI review      | Live pending     | Requires cloud evaluation outputs and a reviewed analysis of protected/sensitive attributes before promotion.                                       | Approved review artifact                      |

### Overall Phase 11: Deploy Online and Batch Endpoints

| Granular task                           | Status           | What was done and why                                                                                                                         | Evidence and validation                        |
| --------------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------- |
| Validate online requests                | Offline complete | Requires a non-empty JSON record list, rejects leakage, and returns labels plus positive-class probabilities.                                 | `deployment/online/score.py`, contract tests |
| Score batch CSV inputs                  | Offline complete | Loads the model once, rejects leakage, accepts optional labels, and emits source, prediction, and probability rows.                           | `deployment/batch/score.py`                  |
| Define environment-specific deployments | Offline complete | Development, staging, and production have checked capacity, concurrency, timeout, retry, and private-access settings.                         | `deployment/configs/`                        |
| Build endpoint resources                | Offline complete | Uses AAD authentication, Application Insights, disabled public and egress access, bounded retries, and approved model/environment references. | `deployment/manage_endpoints.py`             |
| Deploy and run endpoint tests           | Live pending     | Private endpoints require a network-capable runner or approved in-network execution.                                                          | Endpoint/deployment IDs and smoke-test run     |

### Overall Phase 12: Release and Roll Back Safely

| Granular task                           | Status           | What was done and why                                                                                                        | Evidence and validation                    |
| --------------------------------------- | ---------------- | ---------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| Create candidate separately             | Offline complete | Endpoint automation creates a named candidate without shifting online traffic, preserving the stable deployment.             | `deployment/manage_endpoints.py`         |
| Calculate complete traffic splits       | Offline complete | Validates 0–100 percent allocation, requires a stable deployment for partial traffic, and prevents self-referential splits. | `deployment/release.py`, release tests   |
| Support canary, promotion, and rollback | Offline complete | Ten percent, 100 percent, and zero percent candidate allocations use the same auditable command.                             | Release CLI and workflow                   |
| Observe and promote production          | Live pending     | Requires production telemetry, a defined observation window, and protected-environment approval.                             | GitHub deployment record and Azure metrics |
| Exercise rollback                       | Live pending     | Must be tested against two actual deployments; documentation alone is insufficient.                                          | Endpoint traffic history and test record   |

## Major Stage E: Operate, Detect, and Recover

**What:** Detects service/model degradation, initiates governed retraining, and
automates delivery while retaining human production controls.

**Why:** Model quality and service health change after release. Operational
ownership and rollback are part of the model lifecycle, not optional extras.

### Overall Phase 13: Monitor, Alert, and Retrain

| Granular task                       | Status           | What was done and why                                                                                              | Evidence and validation                     |
| ----------------------------------- | ---------------- | ------------------------------------------------------------------------------------------------------------------ | ------------------------------------------- |
| Define thresholds                   | Offline complete | Checks PSI, ROC-AUC, recall, error rate, and latency against version-controlled expectations.                      | `configs/monitoring.json`                 |
| Calculate drift deterministically   | Offline complete | Added tested PSI calculation with explicit histogram validation so drift logic is testable without Azure.          | `src/monitoring.py`, monitoring tests     |
| Decide retraining explicitly        | Offline complete | Returns alert reasons and always requires the normal evaluation and staged-release gates for retrained candidates. | `retraining_decision`                     |
| Configure Azure monitors and alerts | Live pending     | Baselines, endpoint data collection, action groups, and owners depend on deployed resources.                       | Azure Monitor/model-monitor resources       |
| Execute governed retraining         | Live pending     | Requires monitored evidence, cloud pipeline execution, approval, and safe release.                                 | New job, model version, and release records |

### Overall Phase 14: Complete CI/CD and Operations

| Granular task                    | Status           | What was done and why                                                                                                                                                                                                                         | Evidence and validation                                                        |
| -------------------------------- | ---------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------ |
| Validate pull requests           | Offline complete | Formatting, linting, typing, tests, SDK imports, container checks, and security scanning provide fast pre-merge feedback. The single MLflow-blocked cryptography advisory has a documented, reachability-based exception and removal trigger. | `.github/workflows/ci.yml`, `docs/dependency-security.md`                  |
| Review and deploy infrastructure | Offline complete | Build and validation precede`what-if`; deployment is explicit and environment-protected.                                                                                                                                                    | `.github/workflows/infrastructure.yml`                                       |
| Submit training                  | Offline complete | A dedicated OIDC workflow accepts immutable asset references and submits a traceable Azure ML job. Asset registration remains an explicit preceding command.                                                                                  | `.github/workflows/train.yml`, `pipelines/register_assets.py`              |
| Release approved models          | Offline complete | A protected workflow deploys candidates, tests staging, and applies explicit canary/promotion/rollback operations.                                                                                                                            | `.github/workflows/release-model.yml`                                        |
| Document operations              | Offline complete | Architecture, governance, incident handling, rollback, retraining, cost, and cleanup procedures are source-controlled.                                                                                                                        | `docs/architecture.md`, `docs/model-governance.md`, `docs/operations.md` |
| Prove end-to-end operation       | Live pending     | Requires successful protected workflows and evidence that another operator can reproduce provision, train, deploy, monitor, and recover.                                                                                                      | GitHub run URLs and Azure resource/job IDs                                     |

## Final Completion Boundary

## Major Stage F: Customer Intelligence Extension

**What:** Adds a separate retail transaction source, 30-day spending
regression, RFM clustering, task-aware tracking/governance/batch scoring, and
historical monitoring replay.

**Why:** Demonstrates that the delivery platform can support classification,
regression, and unsupervised learning without inventing a shared identity
between unrelated bank and retail populations.

| Granular task | Status | What was done and why | Evidence and validation |
|---|---|---|---|
| CI-A.1.1 Verify retail source | Verified locally | Downloads the official UCI archive, verifies archive/workbook hashes, converts the workbook deterministically, and records attribution and source shape. | `scripts/download_online_retail.py`, `data/README.md`; archive `f538...ede8b`, CSV `c359...e69f` |
| CI-A.1.2 Clean transactions | Verified locally | Excludes duplicates, cancellations, unidentified customers, and nonpositive purchases while recording overlapping exclusion counts. | `src/customer_intelligence_data.py`; 392,692 eligible rows and 4,338 customers |
| CI-A.2.1 Build customer snapshots | Verified locally | Aggregates pre-cutoff purchase history into versioned customer features and RFM inputs. | Prepared metadata; unit fixtures for hand-calculated customer values |
| CI-A.2.2 Enforce temporal splits | Verified locally | Uses complete 90-day histories and 30-day outcomes with train outcomes ending before validation and validation outcomes ending before test. | 9,620 train, 4,074 validation, 2,461 test rows; repeatable hashes |
| CI-B.1.1 Compare regression candidates | Verified locally | Compares ridge, regularized histogram boosting, and log-target random forest against mean and past-spend-rate baselines. | `src/customer_intelligence_regression.py`; selected `random_forest_log` |
| CI-B.2.1 Gate regression | Verified locally, approved | Applies validation improvement and final MAE/RMSE baseline-ratio gates in original GBP units. | Test MAE `311.29`, RMSE `1097.59`, R-squared `0.3679`, approved report |
| CI-C.1.1 Compare K-means candidates | Verified locally | Applies a fitted Yeo-Johnson transform and compares seeded `k=2..6` candidates. | `src/customer_intelligence_clustering.py`; selected `k=2` |
| CI-C.1.2 Gate clustering | Verified locally, approved | Checks silhouette, Davies-Bouldin, minimum size, and adjusted-Rand stability; emits review-required profiles. | Silhouette `0.4358`, Davies-Bouldin `0.9327`, minimum fraction `0.3885`, stability `1.0` |
| CI-D.1.1 Track task lifecycles | Verified locally | Logs task tags, source/data lineage, dependencies, parameters, metrics, models, evaluations, and release evidence in separate descriptive MLflow runs. | Repeatable run pairs `71b64...`/`1a9d0...` and `bdd4f...`/`ddcb6...` |
| CI-D.1.2 Govern task evidence | Verified locally | Validates task-specific metric sets and retains backward-compatible classification evidence. | `src/register_model.py`, `src/customer_intelligence_release.py`, registration tests |
| CI-D.2.1 Score retail batches | Verified locally | Regression returns nonnegative GBP predictions; clustering returns version-local assignments and centroid distance with customer/cutoff lineage. | Real saved-model round-trip validation and batch contract tests |
| CI-E.1.1 Fit drift references | Verified locally | Freezes quantile buckets and applies PSI with sample-size and finite-value checks. | `src/customer_intelligence_monitoring.py`, monitoring tests |
| CI-E.2.1 Monitor regression | Historical replay verified | Matches fully observed outcomes and compares MAE with the frozen baseline. | Maximum feature PSI `0.0751`; MAE ratio `0.9581`; no alert |
| CI-E.2.2 Monitor clustering | Historical replay verified | Tracks RFM drift, assignment proportions, and centroid-distance ratio without comparing raw IDs across model versions. | Maximum feature PSI `0.1349`; assignment PSI near zero; distance ratio `0.9171`; no alert |
| CI-F.1.1 Extend runtime and CI | Offline complete; build pending | Pins NumPy/OpenPyXL, expands tests/import checks, and includes retail scoring code in the non-root image. | 52 pytest tests, Ruff, mypy, and static container contracts pass; local Docker build is blocked because the Docker Desktop Linux engine is not running |
| CI-F.2.1 Add Azure contracts | Offline complete | Adds parallel Azure ML component branches, task-aware asset/submission options, protected batch release workflow, and task-specific scoring scripts. | `pipelines/azureml_pipeline.py`, `.github/workflows/train.yml`, `.github/workflows/release-customer-intelligence.yml` |
| CI-F.2.2 Prove live operation | Live pending | Requires explicit authorization for Azure jobs, model registration, batch deployment/invocation, and production monitoring. | No retail Azure job or deployment IDs claimed |
| CI-G.1.1 Record outcomes | Verified locally | Updates dataset, architecture, operations, extension, phase, and implementation records with limitations and evidence. | Source-controlled documentation |

The [customer-intelligence extension](CUSTOMER_INTELLIGENCE_EXTENSION.md)
retains its own `CI` identifiers. Existing classification and platform
mechanisms are reuse dependencies, not new extension achievements.

Repository implementation and offline validation do not prove live Azure
behavior. The project becomes fully complete only when all **Live pending**
items have durable evidence: deployment IDs, job IDs, asset versions, endpoint
tests, monitoring signals, approval records, and a tested rollback. Until then,
the code is deployable and auditable, but the production lifecycle remains
unverified.
