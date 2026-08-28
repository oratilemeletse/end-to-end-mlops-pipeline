# Machine Learning Problem Definition

## Business Scenario

A bank must prioritize clients for a term-deposit marketing campaign. The
model estimates whether a client is likely to subscribe so campaign resources
can be directed toward more promising contacts.

This is a learning project using historical public data. It is not suitable
for real lending, eligibility, or customer-treatment decisions.

## Prediction

- **Unit of observation:** one historical client campaign observation.
- **Target:** `y`.
- **Positive class:** `yes`, the client subscribed to a term deposit.
- **Task:** binary classification.
- **Decision point:** before the outcome of the current call is known.

The `duration` feature is prohibited because it is only known after the call
and directly leaks information about the target.

## Model Use

The model produces a probability, not an automatic business decision. A
configurable threshold converts that probability into a campaign-priority
label. A human-owned campaign policy remains responsible for deciding how the
score is used.

## Error Costs

- **False negative:** a likely subscriber is not prioritized, losing a
  potential opportunity.
- **False positive:** campaign effort is spent on a client who does not
  subscribe.

Both matter. Recall represents opportunity coverage, while precision
represents campaign efficiency.

## Evaluation Strategy

Accuracy is not sufficient because the positive class is imbalanced. The
project will report:

- Precision.
- Recall.
- F1.
- ROC-AUC.
- Accuracy for context.
- Confusion-matrix counts.
- Threshold-specific metrics.

The initial release gate will be configured rather than embedded in model
code. Provisional learning thresholds are:

- ROC-AUC of at least `0.75`.
- Recall of at least `0.50`.
- Precision of at least `0.25`.

These values are starting hypotheses. They must be reviewed after establishing
the deterministic baseline and must not be tuned against the final test set.

## Data and Modeling Risks

- The data was collected from a Portuguese banking institution from 2008 to
  2010 and may not represent current populations or behavior.
- Demographic attributes can produce unfair or inappropriate segmentation.
- Multiple observations may relate to repeated campaign contacts.
- The full file is ordered by date, so a random split can overstate future
  performance.
- Unknown categorical values are present.
- Campaign policy changes can cause data and concept drift.

Phase 1 will use a deterministic stratified split for a clear local baseline.
A later experiment must compare it with a time-aware holdout before any claim
of production suitability.

## Success Criteria

The Phase 1 model is successful when:

1. Its complete lineage is logged.
2. It excludes prohibited leakage features.
3. It meets the configured metric thresholds on untouched holdout data.
4. Its evaluation report is reproducible.
5. Its limitations are visible alongside its metrics.
