# Customer Intelligence & End-to-End MLOps Platform

## Purpose and Scope

This extension broadens the existing Bank Marketing MLOps project into a
multi-task customer-intelligence platform:

| Capability | Business question | Scope |
|---|---|---|
| Classification | Will a bank client subscribe to a term deposit? | Existing baseline; preserve, do not rebuild or count as new. |
| Regression | How much will an existing retail customer spend in the next 30 days? | New, time-aware supervised pipeline. |
| Clustering | Which retail customers have similar purchasing behavior? | New, customer-segmentation pipeline. |
| Multi-task operations | Can each task be evaluated, tracked, released, and monitored appropriately? | Extend existing MLOps mechanisms; count only the additions. |

**Planning date:** 2026-10-13.
**Implementation status:** Local implementation verified; Azure integration
implemented and offline-tested; live Azure execution pending explicit
authorization and cost approval.

| Capability | Status | Current evidence |
|---|---|---|
| Retail acquisition and temporal preparation | Verified locally | Official archive/workbook hashes, 392,692 eligible transactions, deterministic split hashes |
| Spending regression | Verified locally, approved | Test MAE `311.29` GBP versus baseline `324.91`; R-squared `0.3679` |
| Customer clustering | Verified locally, approved | `k=2`, silhouette `0.4358`, Davies-Bouldin `0.9327`, stability `1.0` |
| MLflow, evidence, registration, and batch contracts | Verified locally/offline | Two repeatable tracked runs per task and real saved-model scoring |
| Monitoring and governed retraining | Historical replay verified | No alert; regression/clustering quality and feature PSI recorded |
| Azure ML jobs, registration, deployment, and live monitoring | Live pending | No retail cloud execution or deployment is claimed |

The existing phase numbering and completion evidence remain in
[PROJECT_PHASES.md](PROJECT_PHASES.md) and
[IMPLEMENTATION_RECORD.md](IMPLEMENTATION_RECORD.md). Extension IDs use `CI`
so they do not overwrite, renumber, or double-count that work.

## Baseline: Reuse, Not New Deliverables

| Existing mechanism | Evidence | Extension boundary |
|---|---|---|
| Verified Bank Marketing acquisition and preparation | `data/README.md`, `scripts/download_bank_marketing.py`, `src/prepare_data.py` | Add a separate retail acquisition and preparation path. |
| Classification training and evaluation | `src/train.py`, `src/evaluate.py`, `configs/local.json` | Preserve the existing target, metrics, leakage rule, and CLI behavior. |
| MLflow lifecycle and release evidence | `pipelines/run_local.py`, `pipelines/mlflow_tracking.py` | Add regression/clustering runs, signatures, metrics, and task metadata. |
| Governed registration | `src/register_model.py` | Add task-aware evidence validation and model descriptions. |
| Drift and retraining decisions | `src/monitoring.py`, `configs/monitoring.json` | Reuse PSI; add actual reference/current feature processing and task-specific decisions. |
| Container and local quality gates | `docker/Dockerfile`, `pyproject.toml`, `.github/workflows/ci.yml`, `tests/` | Add coverage for new pipelines; do not claim Docker, pytest, or CI as newly introduced. |
| Azure ML assets, jobs, endpoints, release workflows, infrastructure | `pipelines/`, `deployment/`, `infra/`, `.github/workflows/` | Add task-specific integration only; retain existing live-pending gates. |

Existing Azure implementation is not evidence that the new tasks run in Azure.
Finishing an old live-pending checkpoint remains baseline work, not a new
extension deliverable.

## Data Inspection and Recommended Regression Problem

The currently available raw dataset is `bank-additional-full.csv`. Its schema
has campaign, demographic, and economic features plus the binary target `y`;
it does not contain transaction amounts, balances, or lifetime-value labels.
Regressing `y`, predicting the prohibited `duration`, or inventing spending
labels would not establish a legitimate customer-value use case.

**Implemented source:** 
[UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)
as a separate public source. Its official
[metadata](https://archive.ics.uci.edu/api/dataset?id=352) describes 541,909
transaction rows from December 2010 through December 2011, with `InvoiceNo`,
`StockCode`, `Description`, `Quantity`, `InvoiceDate`, `UnitPrice`, `CustomerID`,
and `Country`. Prices are in sterling; cancellations are identified by invoice
codes beginning with `c`. DOI: `10.24432/C5BW33`.

Local acquisition verified the 541,909-row, eight-column workbook and the date
range from 2010-12-01 through 2011-12-09. It found 135,080 missing customer IDs
and 1,454 missing descriptions. Cleaning retained 392,692 eligible purchase
rows across 4,338 identified customers. Integrity values and exact handling
rules are in [`data/README.md`](../data/README.md).

### Prediction Contract

- Unit: one known retail customer at a specified prediction cutoff.
- Features: only transactions strictly before the cutoff, initially using a
  90-day history window.
- Target: total eligible purchase value in the following 30 days, in GBP.
- Eligible purchases: positive quantity and positive price, excluding
  cancellation invoices; document this as gross purchase spend, not net revenue.
- Include eligible customers with no subsequent purchases with a zero target.
- Exclude observations whose entire 30-day outcome window is not covered by
  the dataset. Absence beyond the dataset end must not become a zero label.
- Exclude missing customer IDs from customer-level aggregation, record the
  exclusion counts, and never use customer IDs as predictive features.
- Fit preprocessing only on training history. Use chronological train,
  validation, and final test cutoffs, ensuring training target windows finish
  before validation cutoffs and validation target windows finish before test.
- Repeated customers across time are acceptable for this existing-customer
  prediction use case; report that this does not measure cold-start performance.

Start with a constant training-set baseline and a past-spend-rate baseline,
then compare a simple regularized regressor and a tree-based candidate.
Evaluate MAE, RMSE, R-squared when defined, and error by spend band; report
zero-spend prevalence. Do not use MAPE as the primary metric because targets
can be zero. Select and freeze thresholds on validation data, not final test
results. Any target transformation or nonnegative prediction policy must be
recorded and evaluated in the original GBP units.

This is finite-horizon spend prediction, **not customer lifetime value**.
The short historical coverage does not justify a lifetime-value claim.

### Segmentation Contract

Use the same cleaned retail history to calculate recency, frequency, and
monetary value (RFM) at an explicit cutoff. Define recency in days, frequency
as distinct purchase invoices, and monetary value as eligible purchase spend.
Keep customer IDs only for assignment outputs, not as distance features.

Begin with seeded K-means, training-only scaling, and a small documented
candidate range for the number of clusters. Compare silhouette,
Davies-Bouldin, cluster sizes, interpretable RFM profiles, and stability across
seeds or resamples. Define a bounded deterministic sample for expensive
pairwise metrics. Reject degenerate one-cluster or empty-cluster results;
there is no classification-style accuracy for unlabeled segmentation.

Cluster IDs are model-version-local, not permanent business categories.
Compare refits using matched profiles or permutation-invariant measures.
Business labels such as "frequent high spenders" require profile evidence
and review, not an assumed ordering of numeric IDs.

### Platform Boundary

Bank clients and retail customers are unrelated populations. Do not join
their identifiers or present all three outputs as one real customer's record.
The platform shares delivery practices, not a fabricated identity graph.
Retail regression and clustering can share a feature snapshot; bank
classification remains independently configured.

Batch customer-intelligence outputs are the first delivery target. A frontend,
real-time feature store, new infrastructure platform, automatic marketing
actions, and generative-AI features are outside this extension.

## New-Work Hierarchy

The tables retain the original work hierarchy. Current status is recorded at
each major phase. Completion still requires both implementation evidence and
updated documentation; live Azure work is never inferred from offline tests.

### CI-A: Establish Customer-Intelligence Data Contracts

**Status:** Verified locally.

**Outcome and why:** Trustworthy, time-aware customer snapshots prevent
fabricated targets and future-data leakage.

**Inputs/dependencies:** Verified public source metadata; existing provenance
conventions. No Azure resources are required.
**Outputs:** Acquisition manifest, cleaning report, customer snapshots, target
table, and chronological split manifest.

| Step | Granular task | Deliverable and validation |
|---|---|---|
| CI-A.1 Acquire and profile retail data | CI-A.1.1 Verify source and acquire reproducibly | Record license, attribution, checksum, schema, and time coverage; test corrupted inputs and repeat downloads. |
| CI-A.1 Acquire and profile retail data | CI-A.1.2 Define and apply cleaning rules | Record missing IDs, duplicates, cancellations, nonpositive values, and exclusions; test fixtures and exact retained totals. |
| CI-A.2 Construct temporal customer data | CI-A.2.1 Build reusable RFM/history snapshots | Persist cutoff, history bounds, feature definitions, source hash, and customer key; verify hand-calculated fixture values. |
| CI-A.2 Construct temporal customer data | CI-A.2.2 Build 30-day targets and temporal splits | Include known zero-spend customers, reject incomplete outcome windows, and prove feature/label boundaries and train/validation/test separation. |

**Decision/tradeoff:** Add real transaction data rather than repurpose a
classification label. Gross purchases simplify cancellation attribution but
do not measure refunds or profit. Reassess feasibility after actual profiling.
Do not proceed if coverage cannot support separated training and holdouts.

### CI-B: Deliver Evaluated Regression

**Status:** Verified locally and approved by the configured validation/test
gates. The selected log-target random forest achieved validation MAE
improvement `0.1109`, test MAE `311.29` GBP, RMSE `1097.59`, and R-squared
`0.3679`. Test MAE was `0.9581` of the selected baseline and RMSE was `1.1853`
of baseline, within the configured `1.25` bound.

**Outcome and why:** A reproducible spending estimate adds a genuine numeric
prediction task with an explicit business horizon.

**Inputs/dependencies:** CI-A.2.2; temporal snapshots and labels.
**Outputs:** Persisted regression pipeline, predictions, evaluation report,
model card, and approved/rejected candidate evidence.

| Step | Granular task | Deliverable and validation |
|---|---|---|
| CI-B.1 Train and compare spend models | CI-B.1.1 Implement baselines and candidates | Seeded fits with persisted preprocessing; test deterministic outputs and no holdout fitting. |
| CI-B.2 Evaluate and gate regression | CI-B.2.1 Implement regression reports and gates | MAE/RMSE, baseline comparison, defined R-squared, spend-band errors, and versioned validation-selected thresholds; test exact metric values and rejection paths. |
| CI-B.2 Evaluate and gate regression | CI-B.2.2 Record final holdout and limitations | Freeze model selection before final evaluation; retain cutoff/horizon evidence and distinguish forecast value from lifetime value. |

**Decision/tradeoff:** Prefer an explainable baseline before tuning. Do not
invent an absolute GBP acceptance threshold without validation evidence.

### CI-C: Deliver Interpretable Customer Segmentation

**Status:** Verified locally and approved. A Yeo-Johnson transform corrected
the outlier-dominated raw RFM geometry before comparing `k=2..6`; `k=2`
produced silhouette `0.4358`, Davies-Bouldin `0.9327`, minimum cluster fraction
`0.3885`, and adjusted-Rand stability `1.0`.

**Outcome and why:** Unsupervised customer groups support descriptive
intelligence without inventing ground-truth segment labels.

**Inputs/dependencies:** CI-A.2.1; cleaned RFM snapshots. This phase can proceed
independently of regression once its data prerequisite is ready.
**Outputs:** Persisted preprocessing/cluster model, assignments, cluster
profiles, evaluation report, and reviewed segment definitions.

| Step | Granular task | Deliverable and validation |
|---|---|---|
| CI-C.1 Train and evaluate clusters | CI-C.1.1 Implement seeded K-means comparison | Version scaling/transforms and candidate cluster counts; test deterministic fits and valid finite inputs. |
| CI-C.1 Train and evaluate clusters | CI-C.1.2 Evaluate validity and stability | Compute bounded-sample internal metrics, size distribution, and resample/seed stability; test degenerate cases and label-permutation invariance. |
| CI-C.2 Explain and approve segments | CI-C.2.1 Produce profiles and review evidence | Report RFM summaries and assignment counts; configure quality checks and require profile review before promotion. |

**Decision/tradeoff:** K-means is a simple baseline, not proof that customers
form natural groups. Internal metrics must be balanced against usable profiles.

### CI-D: Extend Tracking, Governance, and Batch Delivery

**Status:** Verified locally and offline. Independent reproducibility runs
produced identical data hashes, metrics, and approval decisions. Latest run
IDs are regression `1a9d0097c9a14e02ace7a7bab4b73458` and clustering
`ddcb6b1d842945e6a5a798c6eb0706ca`; the preceding matching runs are recorded
in `IMPLEMENTATION_RECORD.md`.

**Outcome and why:** Make multiple model types traceable without weakening
classification contracts or rebuilding existing infrastructure.

**Inputs/dependencies:** CI-B.2.2 for regression; CI-C.2.1 for clustering.
Each task integration can start when its own model evidence is ready.
**Outputs:** Task-aware run/candidate metadata, registration evidence,
inference contracts, and separate task result tables.

| Step | Granular task | Deliverable and validation |
|---|---|---|
| CI-D.1 Extend MLflow and registration | CI-D.1.1 Add task-specific tracked lifecycles | Log task, dataset, cutoff/horizon, features, seeds, revisions, metrics, signatures, and artifacts; prove two repeatable runs per new task. |
| CI-D.1 Extend MLflow and registration | CI-D.1.2 Version task-aware release evidence | Reject task/metric/artifact mismatches and incomplete provenance; preserve existing classification evidence compatibility with regression tests. |
| CI-D.2 Deliver batch intelligence | CI-D.2.1 Add task-specific scoring contracts | Regression returns spend in GBP; clustering returns assignments and model-version-local profile references; test saved-model round trips and invalid inputs. |
| CI-D.2 Deliver batch intelligence | CI-D.2.2 Publish auditable retail outputs | Join retail spend and segment outputs only on the same retail snapshot/customer key; include cutoff, task, run/model version, and lineage references. Keep bank results separate. |

**Decision/tradeoff:** Extract shared helpers only when actual duplication
appears. Do not force regression or clustering through classification-only
probability responses, `yes` labels, or ROC-AUC gates.

### CI-E: Extend Drift Monitoring and Governed Retraining

**Status:** Historical replay verified. Regression maximum feature PSI was
`0.0751` and clustering maximum feature PSI was `0.1349`; neither exceeded
`0.2`. Regression MAE remained better than baseline, while clustering
assignment PSI was near zero and centroid-distance ratio was `0.9171`.

**Outcome and why:** Detect changes relevant to each new task, not merely
reuse classifier thresholds for unrelated outputs.

**Inputs/dependencies:** CI-D tracked models and scoring outputs; frozen
reference snapshots and versioned feature definitions.
**Outputs:** Monitoring reports, alert reasons, task-aware retraining requests,
and deterministic drift/no-drift demonstrations.

| Step | Granular task | Deliverable and validation |
|---|---|---|
| CI-E.1 Build monitoring inputs | CI-E.1.1 Add reference fitting and windowed drift reports | Freeze training-reference bins, missing/unknown handling, sample minimums, and window boundaries; reuse existing PSI and test shifted, stable, and insufficient-data cases. |
| CI-E.2 Add task-specific quality signals | CI-E.2.1 Monitor regression after labels mature | Match predictions to fully observed 30-day outcomes; calculate MAE/RMSE and spend/prediction drift; report unavailable labels explicitly. |
| CI-E.2 Add task-specific quality signals | CI-E.2.2 Monitor segmentation and route retraining | Monitor RFM drift, assignment proportions, distances, and profile changes; compare versions without equating numeric IDs; test that alerts never bypass approval/release gates. |

**Decision/tradeoff:** Drift is a warning, not proof of accuracy loss. Use
custom signals for clustering rather than claim native classifier monitoring
supports it. Historical replay is a demonstration, not live production proof.

### CI-F: Extend Runtime, CI, and Azure ML Integration

**Status:** Offline complete except for a local image build; live Azure
pending. Python quality checks, 52 tests, static container contracts, local
model/artifact execution, task-aware Azure ML pipeline construction, protected
workflow definitions, and batch scoring contracts are verified without
submitting billable jobs. The Docker build command was attempted but the local
Docker Desktop Linux engine was not running; GitHub CI retains the real build,
non-root, import, and vulnerability checks.

**Outcome and why:** Prove the new tasks work through the established delivery
system while keeping local checks independent of Azure credentials.

**Inputs/dependencies:** CI-D task contracts for integration; CI-E for
monitoring exercises. Existing cloud asset, identity, network, and protected
environment gates remain prerequisites for live operation.
**Outputs:** Multi-task local checks, runnable container paths, Azure ML
contracts/jobs, and task-specific operational evidence.

| Step | Granular task | Deliverable and validation |
|---|---|---|
| CI-F.1 Extend offline delivery | CI-F.1.1 Expand pytest and existing CI/container checks | Cover new preparation, metrics, tracking, scoring, and monitoring; run each task in the existing image with external data mounts and preserve classifier behavior. Add dependencies only if required. |
| CI-F.2 Extend Azure workflows | CI-F.2.1 Add task-specific assets/components and workflow inputs | Reuse environments, OIDC, compute, and governance; validate pipeline construction and task routing offline before authorized submission. |
| CI-F.2 Extend Azure workflows | CI-F.2.2 Prove live new-task operation | Retain Azure job IDs, MLflow runs, asset/model versions, batch results, monitoring signals, and promotion/rollback evidence where applicable. Do not mark live complete from mocks. |

**Decision/tradeoff:** Batch-first delivery reduces serving complexity.
Azure's built-in tabular drift supports classification/regression; batch
inference data collection is our responsibility and clustering needs custom
signals. Recheck supported features before implementation; preview model
performance features are not a mandatory production dependency.

### CI-G: Package Evidence and Update Project Claims

**Status:** Verified locally. Documentation distinguishes baseline reuse,
new extension work, historical replay, offline Azure contracts, and live
pending operations.

**Outcome and why:** Make the finished extension understandable and ensure
portfolio wording corresponds to actual evidence.

**Inputs/dependencies:** Completed task artifacts; CI-F.2.2 for cloud claims.
**Outputs:** Updated architecture/use-case/operations documentation, model
cards, reproducible walkthrough, and an evidence-linked completion record.

| Step | Granular task | Deliverable and validation |
|---|---|---|
| CI-G.1 Document incremental results | CI-G.1.1 Record task outcomes and evidence | For every CI ID, document what/why, inputs/outputs, dependencies, decisions, limitations, commands, and artifact/run links; another operator reproduces the new local tasks. |
| CI-G.2 Publish supported portfolio wording | CI-G.2.1 Review claims against completion evidence | Attribute classification and core tooling to the existing baseline; count only new task pipelines and integration. Distinguish offline demonstrations from live Azure operation. |

## Execution Order and Completion Rules

1. Finish CI-A and confirm retail data feasibility before committing to models.
2. Build CI-B and CI-C from their respective data prerequisites.
3. Integrate each completed task through CI-D, then CI-E.
4. Extend offline runtime/workflow contracts in CI-F before live execution.
5. Finish CI-G with evidence matching the level of completion.

Do not mark a phase complete until its granular tasks and required
documentation are complete. Record separate states for Planned, Implemented
offline, Verified locally, and Verified live; model approval is a separate
result, not an automatic consequence of implementation completion.

No Azure resources, jobs, registrations, deployments, or production monitoring
were created while completing the local/offline extension.

## Portfolio Wording

**Current truthful wording:**

> Customer Intelligence & End-to-End MLOps Platform (2026): Built
> classification, regression, and clustering pipelines; evaluated models and
> implemented MLflow tracking, drift monitoring, Docker, pytest, GitHub Actions
> CI, and Azure Machine Learning workflows.

For detailed discussion, add: regression/clustering and monitoring are locally
verified, while the Azure ML retail workflows remain offline-validated and
await authorized live execution.

**Stronger future wording after live Azure evidence exists:**

> Customer Intelligence & End-to-End MLOps Platform (2026): Built and operated
> governed classification, spending-regression, and customer-segmentation
> pipelines in Azure Machine Learning with protected batch releases and
> production monitoring evidence.

The current sentence describes the resulting repository as a whole. It does
not mean classification, Docker, pytest, CI, or the original Azure foundation
were newly introduced by this extension.

## References

- [Existing classification problem and use boundaries](ML_PROBLEM.md).
- [Existing phase checkpoints](PROJECT_PHASES.md).
- [Existing implementation and live evidence](IMPLEMENTATION_RECORD.md).
- [Retail spending regression model card](models/retail-spending-regression.md).
- [Retail customer segmentation model card](models/retail-customer-segmentation.md).
- [UCI Online Retail source](https://archive.ics.uci.edu/dataset/352/online+retail).
- [UCI Online Retail DOI](https://doi.org/10.24432/C5BW33).
- [Azure ML model monitoring](https://learn.microsoft.com/en-us/azure/machine-learning/concept-model-monitoring?view=azureml-api-2).
