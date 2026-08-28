"""Batch scoring entry point for CSV files."""

from __future__ import annotations

import os
from pathlib import Path

import mlflow.sklearn
import pandas as pd
from sklearn.pipeline import Pipeline

from deployment.online.score import find_model_path

MODEL: Pipeline | None = None


def init() -> None:
    """Load the model once for each batch worker."""
    global MODEL
    model_root = os.getenv("AZUREML_MODEL_DIR", "").strip()
    if not model_root:
        raise ValueError("AZUREML_MODEL_DIR is required")
    MODEL = mlflow.sklearn.load_model(str(find_model_path(Path(model_root))))


def run(mini_batch: list[str]) -> pd.DataFrame:
    """Score a mini-batch and return one row per source record."""
    if MODEL is None:
        raise RuntimeError("Model is not initialized")
    if not mini_batch:
        raise ValueError("mini_batch must contain at least one CSV path")

    outputs: list[pd.DataFrame] = []
    for source in mini_batch:
        frame = pd.read_csv(source)
        if frame.empty:
            continue
        if "duration" in frame.columns:
            raise ValueError(f"Prohibited duration feature found in {source}")
        features = frame.drop(columns=["y"], errors="ignore")
        classes = list(MODEL.classes_)
        if "yes" not in classes:
            raise ValueError("Deployed model does not contain positive class 'yes'")
        probabilities = MODEL.predict_proba(features)[:, classes.index("yes")]
        outputs.append(
            pd.DataFrame(
                {
                    "source_file": Path(source).name,
                    "prediction": MODEL.predict(features),
                    "probability_yes": probabilities,
                }
            )
        )
    if not outputs:
        raise ValueError("No scoreable rows were found in the mini-batch")
    return pd.concat(outputs, ignore_index=True)
