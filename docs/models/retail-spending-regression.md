# Retail Spending Regression Model Card

## Intended Use

Estimate gross purchase spend in GBP for an existing identified Online Retail
customer during the 30 days after a prediction cutoff. The estimate can support
aggregate planning or analyst review. It must not be presented as customer
lifetime value, profit, creditworthiness, or an automatic customer-treatment
decision.

## Data and Split

- Source: UCI Online Retail, DOI `10.24432/C5BW33`.
- Features: eleven purchase-history aggregates from the 90 days strictly
  before each cutoff.
- Target: eligible positive purchase value during the following complete
  30-day window.
- Training cutoffs: April-August 2011.
- Validation cutoffs: September-October 2011.
- Final test cutoff: November 1, 2011.
- Existing-customer scope: customers must have eligible activity in the
  history window; this does not evaluate cold-start customers.

## Model Selection and Metrics

The lifecycle compared a mean baseline, past-spend-rate baseline, ridge,
histogram gradient boosting, and a log-target random forest. Selection used
validation MAE; the final temporal test set was not used to choose the model.

| Metric | Result |
|---|---:|
| Test MAE | `311.2925` GBP |
| Test RMSE | `1097.5919` GBP |
| Test R-squared | `0.3679` |
| Baseline MAE | `324.9053` GBP |
| MAE/baseline ratio | `0.9581` |
| RMSE/baseline ratio | `1.1853` |
| Validation MAE improvement | `0.1109` |
| Approval | Passed |

MAE improved over the selected past-spend-rate baseline. RMSE was worse than
baseline but remained within the configured `1.25` ratio gate, making large
customer errors a visible operational limitation rather than hiding them.

## Reproducibility and Governance

- Configuration: `configs/customer_intelligence.json`.
- Training/evaluation: `src/customer_intelligence_regression.py`.
- Local lifecycle: `pipelines/run_customer_intelligence.py`.
- Latest verified MLflow run: `1a9d0097c9a14e02ace7a7bab4b73458`.
- Release evidence schema: `2.0`, task type `regression`.
- Batch output: nonnegative `predicted_spend_gbp` with customer and cutoff
  lineage columns.

Two independent lifecycle executions produced identical prepared-data hashes,
metrics, and approval decisions.

## Limitations and Monitoring

- Source history covers one retailer and an older one-year period.
- Gross positive purchases exclude cancellations/refunds and do not represent
  margin or profitability.
- Error is concentrated in higher-spend customers.
- Repeated customers across cutoffs are intentional for an existing-customer
  forecasting problem.
- Production use requires feature PSI monitoring and quality evaluation only
  after complete 30-day outcomes become available.
- Retraining alerts never bypass evaluation, registration, or release gates.
