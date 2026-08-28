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
