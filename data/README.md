# Dataset: UCI Bank Marketing

## Selected File

This project uses `bank-additional-full.csv` from the UCI Bank Marketing
dataset. It contains 41,188 observations, 20 input columns, and the binary
target `y`.

The raw file is downloaded locally and is not committed to Git.

## Reproduce the Download

From the repository root:

```powershell
python -m scripts.download_bank_marketing
```

The command:

1. Downloads the official UCI archive.
2. Verifies the outer and nested ZIP SHA-256 checksums.
3. Extracts only `bank-additional-full.csv`.
4. Verifies the CSV checksum and expected shape.
5. Writes the CSV and provenance metadata under `data/raw/`.

Expected output:

```text
data/raw/
|-- bank-additional-full.csv
`-- bank-additional-full.metadata.json
```

## Source and Attribution

- Dataset: [UCI Bank Marketing](https://archive.ics.uci.edu/dataset/222/bank+marketing)
- Dataset DOI: [10.24432/C5K306](https://doi.org/10.24432/C5K306)
- Creators: S. Moro, P. Rita, and P. Cortez
- License: [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/)
- Introductory paper: S. Moro, P. Cortez, and P. Rita, "A data-driven
  approach to predict the success of bank telemarketing," *Decision Support
  Systems*, 2014, DOI
  [10.1016/j.dss.2014.03.001](https://doi.org/10.1016/j.dss.2014.03.001).

## Dataset Integrity

| Artifact | SHA-256 |
|---|---|
| `bank-marketing.zip` | `e0bf5f5de5b846e2f18e9d90606637267d46dfa260e0f17bb12e605db5efbeb4` |
| `bank-additional.zip` | `a607b5edab6c6c75ce09c39142a77702c38123bd5aa7ae89a63503bbe17d65cd` |
| `bank-additional-full.csv` | `74adfc578bf77a7ff4bb1ba4a9f8709d9e3c6907342959c2c8416847e0afb4d8` |

The CSV uses a semicolon delimiter.

## Target and Leakage Rule

The target `y` records whether the client subscribed to a term deposit:

- `yes`: positive class
- `no`: negative class

The `duration` column is excluded from model features. UCI explicitly notes
that call duration is not known before a call is completed and strongly
reveals the result. Using it would create target leakage and an unrealistic
pre-call prediction system.

Unknown categorical values are legitimate values in this dataset and must not
be silently interpreted as missing Python values.

## Data Handling

- Never edit the downloaded CSV manually.
- Re-run the download command to restore it.
- Do not commit files under `data/raw/`.
- Log the CSV checksum, row count, and column count with each MLflow run.
- Later Azure ML phases will register this file as a versioned data asset.

## Prepare the Data

After downloading the raw file, run:

```powershell
python -m src.prepare_data --config configs/local.json
```

This validates the expected schema and target values, removes `duration`,
creates a deterministic stratified split, and writes `train.csv`, `test.csv`,
and `metadata.json` under the ignored `artifacts/prepared/` directory.

The training stage then reads only `artifacts/prepared/train.csv`:

```powershell
python -m src.train --config configs/local.json
```

It preprocesses numeric and categorical columns, trains logistic regression,
and writes a loadable MLflow model under `artifacts/model/baseline/`.

---

# Dataset: UCI Online Retail

## Purpose

The customer-intelligence extension uses Online Retail transactions for two
separate tasks:

- Predict an existing customer's gross purchase spend over the next 30 days.
- Segment customers from recency, purchase frequency, and monetary value.

These retail customers are not joined to Bank Marketing clients.

## Reproduce the Download

```powershell
python -m scripts.download_online_retail
```

The command downloads the official UCI archive, verifies the archive and
workbook, converts the workbook to deterministic UTF-8 CSV, validates its
shape, and writes provenance metadata:

```text
data/raw/
|-- online-retail.csv
`-- online-retail.metadata.json
```

## Source and Integrity

- Dataset: [UCI Online Retail](https://archive.ics.uci.edu/dataset/352/online+retail)
- DOI: [10.24432/C5BW33](https://doi.org/10.24432/C5BW33)
- Creator: Daqing Chen
- License: CC BY 4.0
- Coverage: 2010-12-01 08:26 through 2011-12-09 12:50

| Artifact | SHA-256 |
|---|---|
| `online-retail.zip` | `f5385cbb54bbebf7196389109c6b0621faab0c304e3702548165e71c84aede8b` |
| `Online Retail.xlsx` | `43465a06f2ccf7c8b5bd2892bc7defb52f97487934fe93b16ae4c3936424676d` |
| Generated `online-retail.csv` | `c35975c40d0e1e105090fbb11188a409393055f873841bd012915475fc84e69f` |

The verified source contains 541,909 rows and eight columns. Source profiling
found 135,080 rows without `CustomerID` and 1,454 rows without descriptions.

## Cleaning and Temporal Contracts

Run:

```powershell
python -m src.customer_intelligence_data `
  --config configs/customer_intelligence.json
```

Cleaning retains identified, nonduplicate, noncancellation purchases with
positive quantity and price. The verified local run retained 392,692
transactions across 4,338 customers. Exclusion categories can overlap; their
counts are recorded independently in preparation metadata.

Snapshots use 90 days of history and a fully observed following 30-day target
window. Training cutoffs are April-August 2011, validation cutoffs are
September-October, and the untouched test cutoff is November 1. Training
outcomes end before validation features, and validation outcomes end before
test features. Known customers without a purchase in a complete outcome
window receive a zero target; incomplete future windows are rejected.

The generated files under `artifacts/customer_intelligence/prepared/` are:

- `train.csv`: 9,620 rows.
- `validation.csv`: 4,074 rows.
- `test.csv`: 2,461 rows.
- `clustering.csv`: 2,461 customers at the November 1 cutoff.
- `cleaned_transactions.csv` and `metadata.json`.
