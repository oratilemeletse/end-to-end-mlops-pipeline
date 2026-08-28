# Operations Runbook

## Preconditions

- An authorized Azure subscription and the policy-aware infrastructure from
  `infra/`.
- GitHub environments named `dev`, `staging`, and `production`.
- OIDC variables documented in `infra/README.md`.
- `AZURE_RESOURCE_GROUP`, `AZURE_ML_WORKSPACE`, `AZURE_ML_COMPUTE`, and endpoint
  names configured as environment variables.
- A runner with private network access for workspace and endpoint operations.

Public GitHub-hosted runners cannot invoke resources that are reachable only
through the private network. Use an approved self-hosted runner inside the
network or an equivalent controlled execution path.

## Provision

1. Run Bicep build and parameter build.
2. Run subscription validation.
3. Review `what-if`.
4. Deploy only through the selected GitHub environment.
5. Capture deployment outputs and configure non-secret GitHub variables.
6. Verify compute minimum nodes are zero and diagnostic settings use
   `allLogs`.

**Why:** Separating validation, review, and deployment prevents an unreviewed
template from creating billable or policy-incompatible resources.

## Register Assets and Train

1. Register a checksum/version-based data asset and the pinned environment.
2. Submit `pipelines.submit_pipeline`.
3. Record the Azure ML job and Studio URLs.
4. Confirm preparation, training, evaluation, and registration dependencies.
5. Compare cloud metrics with the local baseline.
6. Reject the run if lineage or evaluation output is absent.

## Deploy to Staging

1. Select an approved model version and pinned environment version.
2. Create new online and batch deployments with a unique release name.
3. Do not alter production traffic.
4. Run online request-schema, response-shape, invalid-input, and latency smoke
   tests from an in-network runner.
5. Invoke a batch job and verify its output schema and row count.
6. Mark the model `staging` only after both paths pass.

## Canary and Promotion

1. Record the stable and candidate deployment names.
2. Route 10 percent to the candidate.
3. Observe availability, error rate, p95 latency, throughput, prediction
   distribution, and any available quality signals for the approved window.
4. Promote to 100 percent only when checks pass and production approval is
   recorded.
5. Keep the stable deployment until the rollback window closes.

## Rollback

Trigger rollback for failed smoke tests, elevated errors or latency, invalid
response shape, material prediction shift, or quality regression.

```powershell
python -m deployment.release `
  --endpoint <endpoint> `
  --candidate <failed-candidate> `
  --stable <known-good> `
  --candidate-percentage 0
```

After traffic returns to the stable deployment:

1. Verify endpoint health and a known request.
2. Archive the failed candidate without deleting its evidence.
3. Record the incident timeline, trigger, affected versions, traffic changes,
   and recovery result.
4. Do not retry production release until the root cause and new evidence are
   reviewed.

## Monitoring and Retraining

Monitor two separate categories:

- **Service health:** availability, HTTP errors, p95 latency, throughput, and
  resource utilization.
- **Model health:** schema/data quality, input and prediction drift, and
  ROC-AUC/recall when labels arrive.

`configs/monitoring.json` contains version-controlled initial thresholds.
These are hypotheses and must be tuned using observed production behavior.

A drift or quality alert creates a retraining request. It does not directly
replace production. Retraining must produce a new run, new evidence, a new
model version, staging tests, and a staged release.

## Incident Ownership

The production GitHub environment must identify the current service owner and
required reviewer. Alerts need a real action-group destination before go-live.
An unowned alert is a monitoring failure and blocks production readiness.

## Cost and Cleanup

- Keep training compute at zero nodes when idle.
- Delete obsolete endpoint deployments only after rollback retention expires.
- Review NAT gateway, private endpoint, Log Analytics, Application Insights,
  Storage, and Key Vault charges even when no training job runs.
- Delete only the environment-specific resource group resolved from Bicep
  outputs.
- Key Vault purge protection intentionally prevents immediate purge.
