# AI-300 MLOps Delivery Roadmap

## Purpose

This document defines how the repository will evolve from a local scaffold into
an end-to-end Azure Machine Learning system that:

1. Covers the traditional MLOps objectives in Microsoft Exam AI-300.
2. Demonstrates practices used by an actual engineering organization.
3. Remains reproducible, testable, secure, observable, and cost-conscious.

This roadmap intentionally covers MLOps first. Microsoft Foundry and GenAIOps
work will be planned separately after the machine learning lifecycle is
complete.

For the beginner-friendly implementation order and phase gates, use
[Project Phases and Checkpoints](PROJECT_PHASES.md). This roadmap remains the
higher-level architecture and delivery reference.

## Current State

The repository currently contains a verified local lifecycle:

- Verified dataset acquisition and deterministic preparation.
- Mixed-feature scikit-learn model training.
- Threshold-based evaluation and approval evidence.
- Complete local MLflow lineage and model artifacts.
- An Azure ML pipeline definition.
- Azure ML model registration using `DefaultAzureCredential`.
- A pinned, non-root Docker image that executes the local lifecycle.
- Formatting, linting, type checking, tests, Azure SDK import checks, and
  container checks in GitHub Actions.

The local pieces are connected and verified. Important cloud limitations
remain:

- Evaluation is not an Azure ML component and does not control registration.
- Registration does not require evaluation evidence or provenance.
- No Azure resources are provisioned by infrastructure as code.
- No live training job, endpoint deployment, monitoring, rollback, or
  retraining workflow exists.

## Target Lifecycle

The completed system will implement this flow:

```text
Source change
  -> pull-request checks
  -> infrastructure and configuration validation
  -> versioned data validation
  -> Azure ML training pipeline
  -> MLflow experiment tracking
  -> model evaluation and Responsible AI checks
  -> automated quality gate
  -> model registration and versioning
  -> staging endpoint deployment
  -> smoke and integration tests
  -> canary production release
  -> monitoring and alerting
  -> promotion, rollback, or retraining
```

## Target Repository Structure

The implementation should gradually move toward:

```text
.
|-- .github/
|   `-- workflows/
|       |-- ci.yml
|       |-- infrastructure.yml
|       |-- train.yml
|       `-- release-model.yml
|-- components/
|   |-- prepare_data/
|   |-- train_model/
|   |-- evaluate_model/
|   `-- register_model/
|-- configs/
|   |-- development.yml
|   |-- staging.yml
|   `-- production.yml
|-- deployment/
|   |-- batch/
|   |-- online/
|   `-- monitoring/
|-- docker/
|   `-- Dockerfile
|-- docs/
|   |-- AI300_MLOPS_ROADMAP.md
|   |-- architecture.md
|   |-- operations.md
|   `-- model-governance.md
|-- infra/
|   |-- main.bicep
|   |-- modules/
|   `-- parameters/
|-- pipelines/
|   |-- training_pipeline.py
|   `-- submit_pipeline.py
|-- src/
|   `-- shared/
|-- tests/
|   |-- unit/
|   |-- component/
|   |-- integration/
|   `-- contracts/
|-- pyproject.toml
`-- README.md
```

Directories should be introduced only when their corresponding phase begins.
Empty architecture scaffolding should not be created merely to match this
tree.

## Delivery Phases

### Phase 1: Make the Local Lifecycle Executable

**Goal:** Establish a reliable local path from data to evaluated MLflow model.

**Status:** Complete and verified locally. Two independent lifecycle runs
produced identical evaluation metrics and retained separate MLflow run IDs.

Follow the hands-on [Phase 1 tutorial](PHASE1_TUTORIAL.md) for the recommended
learning sequence, checkpoints, and definition of done.

Planned work:

- Define a small, documented dataset and prediction objective.
- Add validated configuration for paths, seeds, parameters, and thresholds.
- Give training and evaluation modules explicit command-line interfaces.
- Split data preparation from model training.
- Persist the trained model in MLflow format.
- Log the random seed, dependency versions, source revision, input data
  reference, parameters, metrics, and model artifact.
- Add threshold-specific metrics and a machine-readable evaluation report.
- Add tests for invalid inputs, deterministic output, evaluation behavior, and
  artifact creation.

Completion criteria:

- A clean checkout can run the complete local lifecycle with one documented
  command.
- Repeated runs with identical inputs produce equivalent results.
- Every run has enough metadata to identify its code, data, configuration, and
  environment.

### Phase 2: Build Reusable Azure ML Components

**Goal:** Convert local stages into independently testable Azure ML components.

Planned work:

- Create components for data preparation, training, evaluation, and
  registration.
- Give every component explicit typed inputs and outputs.
- Use component-specific source directories to keep upload contexts small.
- Define a pinned Azure ML environment.
- Compose the components into a training pipeline.
- Add a separate submission entry point using `MLClient`.
- Validate pipeline construction without requiring a live workspace in unit
  tests.

Completion criteria:

- The pipeline can be constructed locally and submitted to Azure ML through a
  documented command.
- Components are versionable and independently reusable.
- Evaluation output is a required dependency of registration.

### Phase 3: Provision Azure Infrastructure

**Goal:** Make the Azure environment repeatable and secure.

Planned work:

- Add Bicep modules for:
  - Azure Machine Learning workspace.
  - Storage account.
  - Key Vault.
  - Application Insights or Azure Monitor integration.
  - Azure Container Registry when a custom registry is justified.
  - CPU compute cluster with minimum nodes set to zero.
  - Managed identities and least-privilege RBAC assignments.
- Add development, staging, and production parameter files.
- Configure GitHub Actions authentication through workload identity
  federation; do not store Azure client secrets.
- Document optional private networking separately because it increases cost
  and operational complexity.

Completion criteria:

- A new environment can be created from source-controlled templates.
- No subscription identifiers, credentials, tokens, or connection strings are
  committed.
- CI and workloads authenticate through OIDC or managed identity.

### Phase 4: Add Data and Asset Governance

**Goal:** Make inputs and execution environments traceable Azure ML assets.

Planned work:

- Register versioned Azure ML data assets.
- Create and version Azure ML environments and components.
- Record data asset name and version in every MLflow run.
- Demonstrate sharing assets through an Azure ML registry where useful.
- Validate schemas and fail clearly on incompatible data.
- Define retention and archival expectations for data, environments,
  components, runs, and models.

Completion criteria:

- A registered model can be traced to exact data, code, environment,
  parameters, and evaluation evidence.
- Replacing a data asset version produces a distinct, reviewable run.

### Phase 5: Add Experimentation and Optimization

**Goal:** Demonstrate controlled comparison rather than a single baseline run.

Planned work:

- Preserve a named baseline run.
- Add Azure ML sweep-based hyperparameter tuning.
- Compare runs using agreed primary and secondary metrics.
- Add an AutoML experiment as a benchmark, not as an unexplained replacement
  for the explicit training pipeline.
- Document when distributed training would be appropriate; implement it only
  if the selected workload justifies it.

Completion criteria:

- Baseline, tuning, and release-candidate runs are distinguishable.
- Model selection is reproducible and based on declared criteria.
- The winning model retains complete lineage.

### Phase 6: Enforce Evaluation and Registration Gates

**Goal:** Prevent unqualified models from entering the registry.

Planned work:

- Define minimum performance and regression thresholds in configuration.
- Compare a release candidate with the current approved model.
- Add Responsible AI analysis appropriate to the dataset and use case.
- Require evaluation metrics, threshold results, provenance, and model
  artifacts before registration.
- Assign lifecycle labels or tags such as candidate, staging, approved, and
  archived.
- Document model rejection and archival procedures.

Completion criteria:

- Registration fails clearly when evidence is missing or thresholds fail.
- Every registered model has evaluation and provenance metadata.
- Approval decisions can be audited after the fact.

### Phase 7: Deploy Online and Batch Inference

**Goal:** Demonstrate both principal Azure ML inference patterns.

Planned work:

- Deploy a managed online endpoint for low-latency requests.
- Deploy a batch endpoint for asynchronous, high-volume scoring.
- Use managed identity for dependent resource access.
- Add request schema validation and useful error reporting.
- Add smoke, contract, and integration tests.
- Define staging and production deployments separately.

Completion criteria:

- Both endpoint types can be deployed through automation.
- Tests verify response shape, basic quality, and failure handling.
- Deployment configuration is version-controlled and environment-specific.

### Phase 8: Implement Safe Release and Rollback

**Goal:** Release models without replacing production blindly.

Planned work:

- Deploy new models as separate endpoint deployments.
- Route a small percentage of traffic to a candidate deployment.
- Compare health and quality signals during a defined observation window.
- Promote traffic only after automated checks and any required approval.
- Restore traffic to the previous deployment when release criteria fail.
- Retain rollback-compatible model and environment versions.

Completion criteria:

- Production releases use canary or blue-green behavior.
- Rollback is documented, automated, and tested.
- A failed candidate does not destroy the last known-good deployment.

### Phase 9: Monitor and Retrain

**Goal:** Operate the model after deployment.

Planned work:

- Capture endpoint availability, error rate, latency, throughput, and resource
  utilization.
- Monitor input distributions and data quality.
- Measure prediction quality when ground truth becomes available.
- Detect data drift and model performance degradation.
- Define alert thresholds and operational ownership.
- Trigger scheduled or threshold-based retraining.
- Require the same evaluation and release gates for retrained models.

Completion criteria:

- Dashboards and alerts identify operational and model-quality problems.
- Monitoring failures are visible and never silently ignored.
- Retraining cannot bypass validation, registration, or release controls.

### Phase 10: Complete CI/CD and Operational Documentation

**Goal:** Make the lifecycle maintainable by a team.

Planned work:

- Pull-request workflow:
  - Formatting and linting.
  - Type checking.
  - Unit and component tests.
  - Pipeline and configuration validation.
  - Dependency and container security scanning.
- Infrastructure workflow:
  - Bicep validation and what-if review.
  - Environment-scoped deployment approval.
- Training workflow:
  - Submit pipeline and retain the Azure ML job reference.
- Release workflow:
  - Verify model approval.
  - Deploy to staging.
  - Run endpoint tests.
  - Require production approval.
  - Perform canary release and promotion.
- Write architecture, model governance, incident response, rollback, cost, and
  retraining documentation.

Completion criteria:

- Routine delivery does not require undocumented local steps.
- Environment changes and model releases are reviewable.
- A new contributor can operate the project from its documentation.

## Docker Strategy

### Dockerfile

The Dockerfile will remain because containers are standard in real MLOps
systems and useful for:

- Reproducible local execution.
- System-level dependency control.
- Custom Azure ML environments when curated environments are insufficient.
- Testing runtime behavior before cloud execution.

Before production use it must:

- Pin the base image to an intentional version or digest.
- Install pinned production dependencies.
- Use a non-root user.
- Copy only required files.
- Expose a meaningful training or serving entry point.
- Pass container vulnerability scanning.

### Docker Compose

The current Compose file runs only a trainer container and mounts local MLflow
artifacts. That is not enough orchestration to justify Compose permanently.

At Phase 1, choose one of these outcomes:

1. **Expand it for local platform development:** run an MLflow tracking server,
   a supported metadata database, artifact storage, and the trainer.
2. **Remove it:** use documented `docker build` and `docker run` commands for
   the single container.

Compose will not be used for Azure production deployment. Azure ML managed
endpoints provide identity, model association, versioned deployments,
autoscaling, traffic splitting, health information, and rollback controls
that Compose does not provide.

## Current File Disposition

| Current path | Planned treatment |
|---|---|
| `src/train.py` | Retain its core logic; add executable inputs, outputs, configuration, and artifact handling during Phase 1. |
| `src/evaluate.py` | Retain and expand; produce evaluation evidence and become an Azure ML component. |
| `src/register_model.py` | Replace direct unconditional registration with a gated registration operation. |
| `pipelines/mlflow_tracking.py` | Retain concepts; expand lineage and consolidate tracking within pipeline execution. |
| `pipelines/azureml_pipeline.py` | Refactor into reusable components plus pipeline composition and submission. |
| `tests/test_train.py` | Retain and expand into unit, component, contract, and integration suites. |
| `.github/workflows/ci.yml` | Retain and expand; add separate infrastructure, training, and release workflows. |
| `docker/Dockerfile` | Retain and harden. |
| `docker/docker-compose.yml` | Removed because the project currently has only one local service. Reintroduce Compose only for a real multi-service local stack. |
| `requirements.txt` | Replace or generate from pinned dependency management defined by `pyproject.toml`. |

## AI-300 MLOps Coverage

The completed phases cover the machine learning portions of AI-300 as follows:

| AI-300 objective | Project evidence |
|---|---|
| Create and manage Azure ML resources | Bicep-provisioned workspace, storage, compute, identity, and networking |
| Create and manage workspace assets | Versioned data, environments, components, models, and registry usage |
| Implement infrastructure as code | Bicep, Azure CLI, GitHub OIDC, and deployment workflows |
| Orchestrate model training | Components, pipelines, MLflow, sweeps, AutoML comparison, and run comparison |
| Register and version models | Evidence-based registration, lifecycle tags, archival, and lineage |
| Deploy models | Managed online and batch endpoints with staged releases |
| Monitor and maintain models | Operational metrics, drift, quality monitoring, alerts, and retraining |

AI-300 also contains substantial Microsoft Foundry and GenAIOps objectives.
Those remain out of scope for this roadmap and must be completed before
claiming full exam coverage.

## Enterprise Practices Beyond Exam Coverage

The project should explicitly demonstrate these real-company concerns:

- Least-privilege access and separation of environments.
- Pull-request review and protected production deployments.
- Cost controls such as zero-minimum training compute and cleanup procedures.
- Clear ownership of alerts and production incidents.
- Data, model, and environment retention policies.
- Auditability of approvals and releases.
- Recovery from bad models, bad data, infrastructure failures, and monitoring
  failures.
- Documentation explaining tradeoffs, not only setup commands.

## Scope Boundaries

The project will not initially:

- Build a custom Kubernetes platform when managed Azure ML capabilities are
  sufficient.
- Use Docker Compose as a production orchestrator.
- Add distributed training merely to check an exam topic.
- Enable expensive private networking without documenting cost and purpose.
- Couple unit tests to a live Azure subscription.
- Register or deploy models that lack metrics and provenance.
- Store secrets or Azure credentials in source control.

## Definition of Done

The MLOps roadmap is complete when:

1. Infrastructure can be recreated from source-controlled templates.
2. A versioned data asset can trigger a reproducible Azure ML training
   pipeline.
3. Every run logs complete parameters, metrics, data references, source
   revision, environment, and artifacts.
4. Registration requires evaluation and provenance.
5. Approved models deploy to online and batch endpoints through CI/CD.
6. Production releases support staged traffic and tested rollback.
7. Operational metrics, drift, and model quality are monitored.
8. Alerts can initiate a governed retraining workflow.
9. Local logic is tested without requiring Azure, while integration tests
   validate real cloud behavior in controlled environments.
10. Documentation enables another engineer to provision, train, release,
    monitor, and recover the system.
