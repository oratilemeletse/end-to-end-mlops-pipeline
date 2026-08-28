"""Train and persist a reproducible mixed-feature classification model."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import mlflow.sklearn
import pandas as pd
from mlflow.models import infer_signature
from sklearn.base import ClassifierMixin
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler


@dataclass(frozen=True)
class TrainingConfig:
    """Validated settings for the model training stage."""

    target_column: str
    random_state: int
    max_iter: int
    regularization_strength: float
    class_weight: str | None
    model_output: Path


def train_model(
    features: pd.DataFrame,
    target: pd.Series,
    *,
    random_state: int = 42,
    max_iter: int = 1_000,
    regularization_strength: float = 1.0,
    class_weight: str | None = None,
) -> Pipeline:
    """Fit preprocessing and logistic regression for mixed feature types."""
    if features.empty:
        raise ValueError("features must contain at least one row")
    if len(features) != len(target):
        raise ValueError("features and target must contain the same number of rows")
    if target.isna().any():
        raise ValueError("target must not contain missing values")
    if target.nunique() != 2:
        raise ValueError("target must contain exactly two classes")
    if max_iter <= 0:
        raise ValueError("max_iter must be greater than zero")
    if regularization_strength <= 0:
        raise ValueError("regularization_strength must be greater than zero")

    numeric_columns = list(features.select_dtypes(include="number").columns)
    categorical_columns = [
        column for column in features.columns if column not in numeric_columns
    ]
    if not numeric_columns and not categorical_columns:
        raise ValueError("features must contain at least one usable column")

    transformers: list[tuple[str, Pipeline, list[str]]] = []
    if numeric_columns:
        numeric_pipeline = Pipeline(
            steps=[
                ("impute", SimpleImputer(strategy="median")),
                ("scale", StandardScaler()),
            ]
        )
        transformers.append(("numeric", numeric_pipeline, numeric_columns))
    if categorical_columns:
        categorical_pipeline = Pipeline(
            steps=[
                ("impute", SimpleImputer(strategy="most_frequent")),
                (
                    "encode",
                    OneHotEncoder(handle_unknown="ignore"),
                ),
            ]
        )
        transformers.append(("categorical", categorical_pipeline, categorical_columns))

    model: Pipeline = Pipeline(
        steps=[
            (
                "preprocess",
                ColumnTransformer(
                    transformers=transformers,
                    remainder="drop",
                ),
            ),
            (
                "classifier",
                LogisticRegression(
                    C=regularization_strength,
                    class_weight=class_weight,
                    max_iter=max_iter,
                    random_state=random_state,
                ),
            ),
        ]
    )
    return model.fit(features, target)


def get_classifier(model: Pipeline) -> ClassifierMixin:
    """Return the fitted classifier from the training pipeline."""
    return model.named_steps["classifier"]


def sha256(path: Path) -> str:
    """Return the lowercase SHA-256 digest for a file."""
    digest = hashlib.sha256()
    with path.open("rb") as file_handle:
        for chunk in iter(lambda: file_handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_training_config(path: Path) -> TrainingConfig:
    """Load and validate model settings from checked JSON configuration."""
    if not path.exists():
        raise FileNotFoundError(f"Configuration file does not exist: {path}")

    raw = json.loads(path.read_text(encoding="utf-8"))
    try:
        data = raw["data"]
        training = raw["training"]
        class_weight_value = training["class_weight"]
        config = TrainingConfig(
            target_column=str(data["target_column"]),
            random_state=int(data["random_state"]),
            max_iter=int(training["max_iter"]),
            regularization_strength=float(training["regularization_strength"]),
            class_weight=(
                None if class_weight_value is None else str(class_weight_value)
            ),
            model_output=Path(training["model_output"]),
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid training configuration in {path}: {error}"
        ) from error

    if config.max_iter <= 0:
        raise ValueError("training.max_iter must be greater than zero")
    if config.regularization_strength <= 0:
        raise ValueError("training.regularization_strength must be greater than zero")
    if config.class_weight not in {None, "balanced"}:
        raise ValueError("training.class_weight must be null or 'balanced'")
    return config


def save_mlflow_model(
    model: Pipeline,
    features: pd.DataFrame,
    output_path: Path,
) -> None:
    """Persist a fitted pipeline in MLflow model format."""
    if output_path.exists():
        if not output_path.is_dir():
            raise ValueError(
                f"Model output exists and is not a directory: {output_path}"
            )
        shutil.rmtree(output_path)

    input_example = features.head(5)
    signature = infer_signature(
        input_example,
        model.predict(input_example),
    )
    pip_requirements = [
        f"mlflow=={importlib.metadata.version('mlflow')}",
        f"pandas=={importlib.metadata.version('pandas')}",
        f"scikit-learn=={importlib.metadata.version('scikit-learn')}",
        f"skops=={importlib.metadata.version('skops')}",
    ]
    mlflow.sklearn.save_model(
        sk_model=model,
        path=str(output_path),
        signature=signature,
        input_example=input_example,
        serialization_format=mlflow.sklearn.SERIALIZATION_FORMAT_SKOPS,
        skops_trusted_types=["numpy.dtype"],
        pip_requirements=pip_requirements,
    )


def train_from_paths(
    training_data: Path,
    model_output: Path,
    config_path: Path,
) -> dict[str, Any]:
    """Train from prepared CSV data and write a loadable MLflow model."""
    if training_data.is_dir():
        training_data = training_data / "train.csv"
    if not training_data.exists():
        raise FileNotFoundError(
            f"Training data does not exist: {training_data}. "
            "Run python -m src.prepare_data first."
        )

    config = load_training_config(config_path)
    data = pd.read_csv(training_data)
    if config.target_column not in data.columns:
        raise ValueError(
            f"Target column is missing from training data: {config.target_column}"
        )
    if "duration" in data.columns:
        raise ValueError("Training data contains prohibited leakage feature: duration")

    features = data.drop(columns=[config.target_column])
    target = data[config.target_column]
    model = train_model(
        features,
        target,
        random_state=config.random_state,
        max_iter=config.max_iter,
        regularization_strength=config.regularization_strength,
        class_weight=config.class_weight,
    )
    save_mlflow_model(model, features, model_output)

    numeric_columns = list(features.select_dtypes(include="number").columns)
    categorical_columns = [
        column for column in features.columns if column not in numeric_columns
    ]
    metadata: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "training_data": {
            "path": str(training_data),
            "sha256": sha256(training_data),
            "rows": len(data),
        },
        "target_column": config.target_column,
        "target_counts": {
            str(label): int(count)
            for label, count in target.value_counts().sort_index().items()
        },
        "features": {
            "total": len(features.columns),
            "numeric": numeric_columns,
            "categorical": categorical_columns,
            "prohibited": ["duration"],
        },
        "parameters": {
            "algorithm": "logistic_regression",
            "random_state": config.random_state,
            "max_iter": config.max_iter,
            "regularization_strength": config.regularization_strength,
            "class_weight": config.class_weight,
        },
        "model_output": str(model_output),
        "format": "mlflow_model",
    }
    (model_output / "training_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Train and save the Bank Marketing baseline model."
    )
    parser.add_argument(
        "--training-data",
        type=Path,
        default=Path("artifacts/prepared/train.csv"),
        help="Prepared training CSV path.",
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=None,
        help="MLflow model output directory; defaults to configuration.",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/local.json"),
        help="Path to the checked JSON configuration.",
    )
    return parser.parse_args()


def main() -> None:
    """Run model training and print a concise result."""
    args = parse_args()
    config = load_training_config(args.config)
    model_output = args.model_output or config.model_output
    metadata = train_from_paths(
        args.training_data,
        model_output,
        args.config,
    )
    print(
        "Model trained: "
        f"{metadata['training_data']['rows']} rows, "
        f"{metadata['features']['total']} features"
    )
    print(f"MLflow model: {model_output}")


if __name__ == "__main__":
    main()
