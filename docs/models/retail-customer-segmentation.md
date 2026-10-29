# Retail Customer Segmentation Model Card

## Intended Use

Describe groups of identified Online Retail customers with similar recency,
purchase-frequency, and monetary-value behavior at an explicit cutoff. The
output supports exploratory customer intelligence and reviewed batch analysis.
It must not automatically determine customer treatment or be presented as
ground-truth customer categories.

## Data and Features

- Source: the same verified UCI Online Retail purchase data used by regression.
- Snapshot cutoff: November 1, 2011.
- History: eligible purchases during the preceding 90 days.
- Features: recency in days, distinct purchase invoices, and gross purchase
  value in GBP.
- Customer IDs are retained only in assignment outputs and are never distance
  features.

## Model Selection and Metrics

A fitted Yeo-Johnson transform standardizes the skewed RFM geometry before
seeded K-means. Candidate cluster counts `2` through `6` were compared using
internal validity, minimum size, and refit stability. The approved model uses
two clusters.

| Metric | Result |
|---|---:|
| Silhouette | `0.4358` |
| Davies-Bouldin | `0.9327` |
| Minimum cluster fraction | `0.3885` |
| Adjusted-Rand stability | `1.0` |
| Mean centroid distance | `1.1296` |
| Approval | Passed |

The larger group contains 1,505 customers with lower purchase frequency and
monetary value; the second contains 956 customers with more recent, frequent,
and higher-value behavior. These are descriptive profiles, not permanent
business labels.

## Reproducibility and Governance

- Configuration: `configs/customer_intelligence.json`.
- Training/evaluation: `src/customer_intelligence_clustering.py`.
- Local lifecycle: `pipelines/run_customer_intelligence.py`.
- Latest verified MLflow run: `ddcb6b1d842945e6a5a798c6eb0706ca`.
- Release evidence schema: `2.0`, task type `clustering`.
- Batch output: version-local `cluster_id` and `distance_to_centroid` with
  customer and cutoff lineage columns.

Two independent lifecycle executions produced identical prepared-data hashes,
metrics, profiles, and approval decisions.

## Limitations and Monitoring

- Internal clustering metrics do not prove marketing or commercial value.
- Numeric cluster IDs can change across refits and must not be compared as
  semantic labels.
- Business names require human review of the versioned profiles.
- K-means still imposes a centroid-based partition even when natural customer
  groups may have different shapes.
- Monitoring uses feature PSI, assignment-mix PSI, and centroid-distance ratio
  for one fixed model version. New model versions require profile matching or
  another permutation-invariant comparison.
- Retraining alerts never bypass evaluation, registration, or release gates.
