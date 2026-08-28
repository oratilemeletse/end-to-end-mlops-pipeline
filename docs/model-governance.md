# Model Governance

## Registration Gate

A model can be registered only when `release_candidate.json` contains:

- `approved: true`;
- non-empty evaluation metrics and threshold results;
- the MLflow run ID and model artifact URI;
- the source-data reference;
- the source revision;
- dependency or environment versions; and
- training parameters.

Validation occurs before `MLClient` is constructed. Missing or rejected
evidence therefore fails without making an Azure request.

## Registry Metadata

Each model version carries:

- lifecycle stage;
- MLflow run ID;
- source revision;
- data reference;
- approval state;
- evaluation metrics;
- training parameters;
- dependency versions; and
- original artifact URI.

These fields make the registry entry an auditable index, not the sole copy of
the underlying evidence. Full reports remain attached to the originating run.

## Lifecycle States

| State | Meaning | Allowed transition |
|---|---|---|
| `candidate` | Passed configured evaluation and entered the registry | staging or archived |
| `staging` | Deployed to a non-production endpoint and tested | approved or archived |
| `approved` | Authorized for controlled production traffic | archived |
| `archived` | Retained for audit or rollback history but not eligible for new release | none without a new review |

Training success alone never grants a lifecycle state.

## Promotion Requirements

1. Evaluation evidence is complete and approved.
2. Data, source, environment, parameters, and run are traceable.
3. Responsible AI limitations are reviewed for the candidate.
4. Staging online and batch tests pass.
5. A production reviewer authorizes canary traffic.
6. Health and quality signals remain within thresholds during the observation
   window.
7. Promotion and rollback targets are recorded.

## Rejection and Archival

- A failed quality threshold rejects registration.
- Missing evidence is an operational failure, not a reason to default to
  approval.
- A candidate that fails staging or canary checks is assigned `archived` and
  retains its reports for diagnosis.
- Registered versions are not deleted merely to hide failed experiments.
- Retention duration must follow organization policy; this learning repository
  does not invent a legal retention period.

## Responsible AI Boundary

The historical dataset includes demographic attributes and may encode outdated
or unfair campaign patterns. Before production approval, compare performance
across reviewed groups, document material disparities, and decide whether
features should be excluded or policy constraints added. This model must not
be used for lending, eligibility, or automatic customer treatment.
