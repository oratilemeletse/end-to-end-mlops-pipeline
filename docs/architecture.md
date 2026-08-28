# Architecture

## Lifecycle

```text
UCI source
  -> checksum-verified raw data
  -> versioned Azure ML data asset
  -> preparation component
  -> training component
  -> MLflow model
  -> evaluation component
  -> release evidence and approval gate
  -> Azure ML model version
  -> staging online and batch deployments
  -> endpoint tests
  -> canary production traffic
  -> monitoring
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

## Main Contracts

| Stage | Inputs | Outputs | Failure boundary |
|---|---|---|---|
| Acquire | Official UCI URL and expected checksums | Raw CSV and provenance | Checksum or shape mismatch |
| Prepare | Raw CSV and checked configuration | Train/test CSVs and metadata | Schema, target, or leakage violation |
| Train | Prepared training data and parameters | MLflow model and training metadata | Missing data or invalid model parameters |
| Evaluate | Model, untouched test data, thresholds | Metrics, confusion counts, approval report | Invalid model output or test schema |
| Register | Model, approval report, complete provenance | Tagged Azure ML model version | Rejection, missing evidence, or missing artifact |
| Deploy | Approved model version, environment, endpoint config | Candidate online/batch deployments | Invalid configuration or Azure deployment failure |
| Release | Stable/candidate names and percentage | Complete endpoint traffic split | Invalid allocation or missing stable deployment |
| Monitor | Endpoint telemetry, drift baseline, labels | Alerts and retraining decision | Missing metrics or invalid monitoring data |

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
