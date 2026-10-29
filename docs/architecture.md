# Architecture

## Lifecycles

```text
UCI Bank Marketing
  -> checksum-verified raw data
  -> classification preparation/training/evaluation
  -> classification MLflow model and release evidence

UCI Online Retail
  -> verified workbook and deterministic CSV
  -> cleaned purchase transactions
  -> time-aware customer snapshots
  -> spending regression branch
  -> RFM clustering branch
  -> task-specific MLflow models and release evidence

Approved model evidence
  -> versioned Azure ML data asset
  -> governed task-specific Azure ML component graph
  -> Azure ML model version
  -> classification online/batch or retail batch deployment
  -> endpoint tests
  -> classification canary traffic or protected retail batch release
  -> service, drift, and task-quality monitoring
  -> rollback or governed retraining
```

## Design Decisions

- Local stage functions remain independently testable and are reused by Azure
  ML command components. This avoids maintaining separate local and cloud ML
  logic.
- All component boundaries use declared Azure ML inputs and outputs. Evaluation
  consumes the exact preparation and model outputs, and registration consumes
  evaluation evidence, preventing hidden path coupling.
- Workspace identifiers are supplied through environment variables, while
  credentials come from `DefaultAzureCredential`. GitHub uses OIDC and Azure
  workloads use managed identity.
- The Azure ML workspace and dependent services use private networking because
  the reviewed subscription policies disable public access and Storage keys.
- Online and batch deployments are separate because latency-sensitive requests
  and asynchronous high-volume scoring have different scaling and retry needs.
- New online deployments receive no traffic during creation. Traffic changes
  are separate release actions so deployment failure cannot replace the
  known-good version.
- Bank and retail identities remain separate. The shared platform standardizes
  lineage, gates, and operations; it does not create a cross-dataset customer
  identity graph.
- Regression uses chronological 90-day history and 30-day outcome windows.
  Training outcomes finish before validation features, and validation
  outcomes finish before final test features.
- Clustering applies a fitted Yeo-Johnson transform before seeded K-means to
  prevent a handful of high-spend customers from collapsing the segment-size
  gate. Cluster IDs remain model-version-local.
- Retail delivery is batch-first. Regression and clustering have distinct
  output schemas instead of being forced through classifier probabilities.

## Main Contracts

| Stage | Inputs | Outputs | Failure boundary |
|---|---|---|---|
| Acquire | Official UCI URL and expected checksums | Raw CSV and provenance | Checksum, workbook, or shape mismatch |
| Prepare | Raw data and checked task configuration | Classification split or temporal customer snapshots | Schema, target, coverage, or leakage violation |
| Train | Prepared task data and parameters | Task-specific MLflow model and metadata | Missing data, invalid parameters, or degenerate clusters |
| Evaluate | Model, holdout/snapshot, task thresholds | Classification, regression, or clustering approval report | Invalid outputs, failed baseline/quality gate, or unusable segments |
| Register | Model, approval report, complete provenance | Tagged Azure ML model version | Rejection, missing evidence, or missing artifact |
| Deploy | Approved model version, environment, endpoint config | Classification online/batch or retail batch candidate | Invalid configuration or Azure deployment failure |
| Release | Stable/candidate names and percentage | Complete endpoint traffic split | Invalid allocation or missing stable deployment |
| Monitor | Frozen feature reference, predictions/assignments, matured labels | Task-aware alert and governed retraining decision | Missing labels, insufficient samples, or invalid monitoring data |

## Security and Reliability

- Secrets, tokens, and subscription-specific values are not committed.
- Data-plane access uses Azure RBAC rather than Storage account keys.
- Training compute scales to zero.
- Endpoint requests reject the known leakage feature.
- Registration fails closed.
- Production workflows require protected GitHub environments.
- Monitoring-triggered retraining uses the same evaluation, registration, and
  release controls as manually initiated candidates.

## Source References

The implementation follows Azure ML SDK v2 patterns documented by Microsoft:

- [Create and run pipelines using components](https://learn.microsoft.com/azure/machine-learning/how-to-create-component-pipeline-python?view=azureml-api-2)
- [Deploy models to online endpoints](https://learn.microsoft.com/azure/machine-learning/how-to-deploy-online-endpoints?view=azureml-api-2)
- [Deploy models to batch endpoints](https://learn.microsoft.com/azure/machine-learning/how-to-use-batch-model-deployments?view=azureml-api-2)
- [Monitor model performance](https://learn.microsoft.com/azure/machine-learning/how-to-monitor-model-performance?view=azureml-api-2)
