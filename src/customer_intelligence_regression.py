"""Train and evaluate next-30-day retail spending regression."""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer, TransformedTargetRegressor
from sklearn.ensemble import HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.linear_model import Ridge
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from src.customer_intelligence_data import (
    IDENTIFIER_COLUMNS,
    REGRESSION_FEATURES,
    TARGET_COLUMN,
    load_retail_config,
)
from src.prepare_data import sha256
from src.train import save_mlflow_model

SUPPORTED_MODELS = {"ridge", "hist_gradient_boosting", "random_forest_log"}


@dataclass(frozen=True)
class RegressionConfig:
    """Validated regression training and release settings."""

    model_output: Path
    evaluation_output: Path
    candidate_models: tuple[str, ...]
    ridge_alpha: float
    hist_max_iter: int
    random_forest_estimators: int
    random_forest_min_samples_leaf: int
    random_forest_max_features: float
    minimum_validation_mae_improvement_fraction: float
    maximum_test_mae_to_baseline_ratio: float
    maximum_test_rmse_to_baseline_ratio: float
    history_days: int
    horizon_days: int
    random_state: int


def load_regression_config(path: Path) -> RegressionConfig:
    """Load and validate regression settings."""
    if not path.exists():
        raise FileNotFoundError(f"Configuration file does not exist: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    retail = load_retail_config(path)
    try:
        settings = raw["regression"]
        config = RegressionConfig(
            model_output=Path(settings["model_output"]),
            evaluation_output=Path(settings["evaluation_output"]),
            candidate_models=tuple(
                str(value) for value in settings["candidate_models"]
            ),
            ridge_alpha=float(settings["ridge_alpha"]),
            hist_max_iter=int(settings["hist_max_iter"]),
            random_forest_estimators=int(settings["random_forest_estimators"]),
            random_forest_min_samples_leaf=int(
                settings["random_forest_min_samples_leaf"]
            ),
            random_forest_max_features=float(settings["random_forest_max_features"]),
            minimum_validation_mae_improvement_fraction=float(
                settings["minimum_validation_mae_improvement_fraction"]
            ),
            maximum_test_mae_to_baseline_ratio=float(
                settings["maximum_test_mae_to_baseline_ratio"]
            ),
            maximum_test_rmse_to_baseline_ratio=float(
                settings["maximum_test_rmse_to_baseline_ratio"]
            ),
            history_days=retail.history_days,
            horizon_days=retail.horizon_days,
            random_state=retail.random_state,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid regression configuration in {path}: {error}"
        ) from error
    if not config.candidate_models:
        raise ValueError("regression.candidate_models must not be empty")
    unsupported = set(config.candidate_models).difference(SUPPORTED_MODELS)
    if unsupported:
        raise ValueError(
            "Unsupported regression models: " + ", ".join(sorted(unsupported))
        )
    if config.ridge_alpha <= 0:
        raise ValueError("regression.ridge_alpha must be greater than zero")
    if config.hist_max_iter <= 0:
        raise ValueError("regression.hist_max_iter must be greater than zero")
    if config.random_forest_estimators <= 0:
        raise ValueError(
            "regression.random_forest_estimators must be greater than zero"
        )
    if config.random_forest_min_samples_leaf <= 0:
        raise ValueError(
            "regression.random_forest_min_samples_leaf must be greater than zero"
        )
    if not 0 < config.random_forest_max_features <= 1:
        raise ValueError(
            "regression.random_forest_max_features must be between zero and one"
        )
    if not 0 <= config.minimum_validation_mae_improvement_fraction < 1:
        raise ValueError(
            "regression.minimum_validation_mae_improvement_fraction "
            "must be between zero and one"
        )
    if config.maximum_test_mae_to_baseline_ratio <= 0:
        raise ValueError(
            "regression.maximum_test_mae_to_baseline_ratio must be greater than zero"
        )
    if config.maximum_test_rmse_to_baseline_ratio <= 0:
        raise ValueError(
            "regression.maximum_test_rmse_to_baseline_ratio must be greater than zero"
        )
    return config


def validate_regression_data(data: pd.DataFrame) -> None:
    """Validate the prepared regression contract."""
    required = set(IDENTIFIER_COLUMNS + REGRESSION_FEATURES + [TARGET_COLUMN])
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            "Regression data is missing required columns: " + ", ".join(sorted(missing))
        )
    if data.empty:
        raise ValueError("Regression data must contain at least one row")
    numeric = data[REGRESSION_FEATURES + [TARGET_COLUMN]].to_numpy(dtype=float)
    if not np.isfinite(numeric).all():
        raise ValueError("Regression data contains non-finite values")
    if (data[TARGET_COLUMN] < 0).any():
        raise ValueError("Regression target must not contain negative spending")


def build_regression_model(name: str, config: RegressionConfig) -> Pipeline:
    """Construct one deterministic regression candidate."""
    if name not in SUPPORTED_MODELS:
        raise ValueError(f"Unsupported regression model: {name}")
    preprocessing = ColumnTransformer(
        transformers=[
            (
                "numeric",
                Pipeline(
                    [
                        ("impute", SimpleImputer(strategy="median")),
                        ("scale", StandardScaler()),
                    ]
                ),
                REGRESSION_FEATURES,
            )
        ],
        remainder="drop",
    )
    if name == "ridge":
        estimator: Any = TransformedTargetRegressor(
            regressor=Ridge(alpha=config.ridge_alpha),
            func=np.log1p,
            inverse_func=np.expm1,
        )
    elif name == "hist_gradient_boosting":
        estimator = HistGradientBoostingRegressor(
            loss="squared_error",
            max_iter=config.hist_max_iter,
            max_leaf_nodes=15,
            l2_regularization=10.0,
            random_state=config.random_state,
        )
    else:
        estimator = TransformedTargetRegressor(
            regressor=RandomForestRegressor(
                n_estimators=config.random_forest_estimators,
                min_samples_leaf=config.random_forest_min_samples_leaf,
                max_features=config.random_forest_max_features,
                n_jobs=-1,
                random_state=config.random_state,
            ),
            func=np.log1p,
            inverse_func=np.expm1,
        )
    return Pipeline([("preprocess", preprocessing), ("regressor", estimator)])


def regression_metrics(
    target: pd.Series | np.ndarray,
    predictions: np.ndarray,
) -> dict[str, float]:
    """Calculate regression metrics in original GBP units."""
    actual = np.asarray(target, dtype=float)
    predicted = np.asarray(predictions, dtype=float)
    if actual.shape != predicted.shape or actual.size == 0:
        raise ValueError(
            "Regression targets and predictions must align and be non-empty"
        )
    if not np.isfinite(actual).all() or not np.isfinite(predicted).all():
        raise ValueError("Regression metrics require finite values")
    metrics = {
        "mae": float(mean_absolute_error(actual, predicted)),
        "rmse": float(mean_squared_error(actual, predicted) ** 0.5),
    }
    metrics["r2"] = (
        float(r2_score(actual, predicted)) if np.unique(actual).size > 1 else 0.0
    )
    return metrics


def baseline_predictions(
    frame: pd.DataFrame,
    *,
    baseline_name: str,
    training_target_mean: float,
    history_days: int,
    horizon_days: int,
) -> np.ndarray:
    """Return a frozen mean or history-rate spending baseline."""
    if baseline_name == "mean":
        return np.full(len(frame), max(0.0, training_target_mean), dtype=float)
    if baseline_name == "past_spend_rate":
        return (
            frame["monetary_value_gbp"].to_numpy(dtype=float)
            * horizon_days
            / history_days
        )
    raise ValueError(f"Unsupported regression baseline: {baseline_name}")


def train_regression_from_paths(
    prepared_data: Path,
    model_output: Path,
    config_path: Path,
) -> dict[str, Any]:
    """Select on validation data, refit, and persist a regression model."""
    config = load_regression_config(config_path)
    train_path = (
        prepared_data / "train.csv" if prepared_data.is_dir() else prepared_data
    )
    validation_path = train_path.parent / "validation.csv"
    if not train_path.exists() or not validation_path.exists():
        raise FileNotFoundError(
            "Prepared train.csv and validation.csv are required for regression"
        )
    train = pd.read_csv(train_path)
    validation = pd.read_csv(validation_path)
    validate_regression_data(train)
    validate_regression_data(validation)
    train_features = train[REGRESSION_FEATURES].astype(float)
    validation_features = validation[REGRESSION_FEATURES].astype(float)
    train_target = train[TARGET_COLUMN]
    validation_target = validation[TARGET_COLUMN]

    training_mean = float(train_target.mean())
    baseline_results: dict[str, dict[str, float]] = {}
    for baseline_name in ("mean", "past_spend_rate"):
        predictions = baseline_predictions(
            validation,
            baseline_name=baseline_name,
            training_target_mean=training_mean,
            history_days=config.history_days,
            horizon_days=config.horizon_days,
        )
        baseline_results[baseline_name] = regression_metrics(
            validation_target,
            predictions,
        )
    selected_baseline = min(
        baseline_results,
        key=lambda name: baseline_results[name]["mae"],
    )
    reference_mae = baseline_results[selected_baseline]["mae"]
    if reference_mae <= 0:
        raise ValueError("Validation baseline MAE must be greater than zero")

    candidate_results: dict[str, dict[str, float]] = {}
    for model_name in config.candidate_models:
        candidate = build_regression_model(model_name, config)
        candidate.fit(train_features, train_target)
        predictions = np.clip(candidate.predict(validation_features), 0.0, None)
        candidate_results[model_name] = regression_metrics(
            validation_target,
            predictions,
        )
    selected_model_name = min(
        candidate_results,
        key=lambda name: candidate_results[name]["mae"],
    )
    selected_validation_mae = candidate_results[selected_model_name]["mae"]
    validation_improvement = 1.0 - (selected_validation_mae / reference_mae)
    validation_gate_passed = (
        validation_improvement >= config.minimum_validation_mae_improvement_fraction
    )

    refit_data = pd.concat([train, validation], ignore_index=True)
    refit_features = refit_data[REGRESSION_FEATURES].astype(float)
    refit_target = refit_data[TARGET_COLUMN]
    selected_model = build_regression_model(selected_model_name, config)
    selected_model.fit(refit_features, refit_target)
    save_mlflow_model(selected_model, refit_features, model_output)

    metadata: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "task_id": "CI-B.1.1",
        "task_type": "regression",
        "target_column": TARGET_COLUMN,
        "feature_columns": REGRESSION_FEATURES,
        "training_data": {
            "path": str(train_path),
            "sha256": sha256(train_path),
            "rows": len(train),
        },
        "validation_data": {
            "path": str(validation_path),
            "sha256": sha256(validation_path),
            "rows": len(validation),
        },
        "parameters": {
            "selected_model": selected_model_name,
            "candidate_models": list(config.candidate_models),
            "ridge_alpha": config.ridge_alpha,
            "hist_max_iter": config.hist_max_iter,
            "random_forest_estimators": config.random_forest_estimators,
            "random_forest_min_samples_leaf": (config.random_forest_min_samples_leaf),
            "random_forest_max_features": config.random_forest_max_features,
            "random_state": config.random_state,
            "history_days": config.history_days,
            "horizon_days": config.horizon_days,
        },
        "validation": {
            "candidate_metrics": candidate_results,
            "baseline_metrics": baseline_results,
            "selected_baseline": selected_baseline,
            "mae_improvement_fraction": validation_improvement,
            "minimum_mae_improvement_fraction": (
                config.minimum_validation_mae_improvement_fraction
            ),
            "gate_passed": validation_gate_passed,
        },
        "refit_target_mean": float(refit_target.mean()),
        "model_output": str(model_output),
        "format": "mlflow_model",
    }
    (model_output / "training_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def spend_band_errors(
    target: pd.Series,
    predictions: np.ndarray,
) -> dict[str, dict[str, float | int]]:
    """Report MAE for zero, lower-positive, and higher-positive spend."""
    positive = target[target > 0]
    median_positive = float(positive.median()) if not positive.empty else 0.0
    masks = {
        "zero": target == 0,
        "lower_positive": (target > 0) & (target <= median_positive),
        "higher_positive": target > median_positive,
    }
    result: dict[str, dict[str, float | int]] = {}
    for name, mask in masks.items():
        count = int(mask.sum())
        result[name] = {
            "rows": count,
            "mae": (
                float(mean_absolute_error(target.loc[mask], predictions[mask]))
                if count
                else 0.0
            ),
        }
    return result


def evaluate_regression_from_paths(
    model_path: Path,
    prepared_data: Path,
    config_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Evaluate the frozen regression model on the untouched temporal test set."""
    config = load_regression_config(config_path)
    test_path = prepared_data / "test.csv" if prepared_data.is_dir() else prepared_data
    if not model_path.exists():
        raise FileNotFoundError(f"Regression model does not exist: {model_path}")
    if not test_path.exists():
        raise FileNotFoundError(f"Regression test data does not exist: {test_path}")
    metadata_path = model_path / "training_metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Regression metadata does not exist: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    test = pd.read_csv(test_path)
    validate_regression_data(test)
    model = mlflow.sklearn.load_model(str(model_path))
    test_features = test[REGRESSION_FEATURES].astype(float)
    predictions = np.clip(model.predict(test_features), 0.0, None)
    metrics = regression_metrics(test[TARGET_COLUMN], predictions)

    selected_baseline = str(metadata["validation"]["selected_baseline"])
    baseline = baseline_predictions(
        test,
        baseline_name=selected_baseline,
        training_target_mean=float(metadata["refit_target_mean"]),
        history_days=config.history_days,
        horizon_days=config.horizon_days,
    )
    baseline_metrics = regression_metrics(test[TARGET_COLUMN], baseline)
    mae_ratio = metrics["mae"] / baseline_metrics["mae"]
    rmse_ratio = metrics["rmse"] / baseline_metrics["rmse"]
    metrics.update(
        {
            "baseline_mae": baseline_metrics["mae"],
            "baseline_rmse": baseline_metrics["rmse"],
            "mae_to_baseline_ratio": mae_ratio,
            "rmse_to_baseline_ratio": rmse_ratio,
            "validation_mae_improvement_fraction": float(
                metadata["validation"]["mae_improvement_fraction"]
            ),
        }
    )
    checks = {
        "validation_improvement": bool(metadata["validation"]["gate_passed"]),
        "test_mae_to_baseline": (
            mae_ratio <= config.maximum_test_mae_to_baseline_ratio
        ),
        "test_rmse_to_baseline": (
            rmse_ratio <= config.maximum_test_rmse_to_baseline_ratio
        ),
    }
    destination = output_dir or config.evaluation_output
    destination.mkdir(parents=True, exist_ok=True)
    prediction_output = test[IDENTIFIER_COLUMNS + [TARGET_COLUMN]].copy()
    prediction_output["predicted_spend_gbp"] = predictions
    prediction_output["baseline_spend_gbp"] = baseline
    prediction_output.to_csv(destination / "predictions.csv", index=False)
    report: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "task_id": "CI-B.2.1",
        "task_type": "regression",
        "model_path": str(model_path),
        "test_data_path": str(test_path),
        "test_rows": len(test),
        "target_column": TARGET_COLUMN,
        "feature_columns": REGRESSION_FEATURES,
        "metrics": metrics,
        "spend_band_errors": spend_band_errors(test[TARGET_COLUMN], predictions),
        "thresholds": {
            "minimum_validation_mae_improvement_fraction": (
                config.minimum_validation_mae_improvement_fraction
            ),
            "maximum_test_mae_to_baseline_ratio": (
                config.maximum_test_mae_to_baseline_ratio
            ),
            "maximum_test_rmse_to_baseline_ratio": (
                config.maximum_test_rmse_to_baseline_ratio
            ),
        },
        "threshold_checks": checks,
        "approved": all(checks.values()),
        "limitations": [
            "The prediction is 30-day gross purchase spend, not customer lifetime value.",
            "The evaluation covers existing customers with recent purchase history.",
            "Final model selection was frozen before this temporal test evaluation.",
        ],
    }
    (destination / "evaluation_report.json").write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination / "metrics.json").write_text(
        json.dumps(metrics, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def parse_train_args() -> argparse.Namespace:
    """Parse regression training arguments."""
    parser = argparse.ArgumentParser(description="Train retail spending regression.")
    parser.add_argument(
        "--prepared-data",
        type=Path,
        default=Path("artifacts/customer_intelligence/prepared"),
    )
    parser.add_argument(
        "--model-output",
        type=Path,
        default=None,
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/customer_intelligence.json"),
    )
    return parser.parse_args()


def parse_evaluate_args() -> argparse.Namespace:
    """Parse regression evaluation arguments."""
    parser = argparse.ArgumentParser(description="Evaluate retail spending regression.")
    parser.add_argument(
        "--model-input",
        type=Path,
        default=Path("artifacts/customer_intelligence/model/spending-regression"),
    )
    parser.add_argument(
        "--prepared-data",
        type=Path,
        default=Path("artifacts/customer_intelligence/prepared"),
    )
    parser.add_argument("--evaluation-output", type=Path, default=None)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/customer_intelligence.json"),
    )
    return parser.parse_args()


def train_main() -> None:
    """Run regression training."""
    args = parse_train_args()
    config = load_regression_config(args.config)
    metadata = train_regression_from_paths(
        args.prepared_data,
        args.model_output or config.model_output,
        args.config,
    )
    print(
        "Regression training complete: "
        f"{metadata['parameters']['selected_model']}, "
        f"validation gate={metadata['validation']['gate_passed']}"
    )


def evaluate_main() -> None:
    """Run regression evaluation."""
    args = parse_evaluate_args()
    report = evaluate_regression_from_paths(
        args.model_input,
        args.prepared_data,
        args.config,
        args.evaluation_output,
    )
    print(
        "Regression evaluation complete: "
        f"MAE={report['metrics']['mae']:.2f}, "
        f"approved={report['approved']}"
    )
