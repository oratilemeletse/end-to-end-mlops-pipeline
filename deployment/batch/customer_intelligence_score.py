"""Batch scoring for retail spending regression and customer clustering."""

from __future__ import annotations

import os
from pathlib import Path

import mlflow.sklearn
import numpy as np
import pandas as pd
from sklearn.pipeline import Pipeline

from deployment.online.score import find_model_path
from src.customer_intelligence_data import IDENTIFIER_COLUMNS, TARGET_COLUMN

MODEL: Pipeline | None = None
TASK_TYPE = ""


def init() -> None:
    """Load one task-specific model for each Azure ML batch worker."""
    global MODEL, TASK_TYPE
    model_root = os.getenv("AZUREML_MODEL_DIR", "").strip()
    if not model_root:
        raise ValueError("AZUREML_MODEL_DIR is required")
    task_type = os.getenv("CUSTOMER_INTELLIGENCE_TASK", "").strip().lower()
    if task_type not in {"regression", "clustering"}:
        raise ValueError("CUSTOMER_INTELLIGENCE_TASK must be regression or clustering")
    MODEL = mlflow.sklearn.load_model(str(find_model_path(Path(model_root))))
    TASK_TYPE = task_type


def score_frame(
    model: Pipeline,
    frame: pd.DataFrame,
    *,
    task_type: str,
    source_file: str,
) -> pd.DataFrame:
    """Score one prepared customer snapshot with a task-aware contract."""
    if frame.empty:
        raise ValueError("Customer-intelligence input must not be empty")
    if task_type not in {"regression", "clustering"}:
        raise ValueError(f"Unsupported customer-intelligence task: {task_type}")
    expected = list(model.feature_names_in_)
    missing = set(expected).difference(frame.columns)
    if missing:
        raise ValueError(
            "Scoring input is missing model features: " + ", ".join(sorted(missing))
        )
    features = frame[expected].astype(float)
    output = pd.DataFrame({"source_file": [source_file] * len(frame)})
    for column in IDENTIFIER_COLUMNS:
        if column in frame:
            output[column] = frame[column].to_numpy()
    if task_type == "regression":
        output["predicted_spend_gbp"] = np.clip(
            model.predict(features),
            0.0,
            None,
        )
        if TARGET_COLUMN in frame:
            output[TARGET_COLUMN] = frame[TARGET_COLUMN].to_numpy()
    else:
        output["cluster_id"] = model.predict(features).astype(int)
        output["distance_to_centroid"] = model.transform(features).min(axis=1)
    return output


def run(mini_batch: list[str]) -> pd.DataFrame:
    """Score prepared customer CSV files and preserve lineage columns."""
    if MODEL is None or not TASK_TYPE:
        raise RuntimeError("Customer-intelligence model is not initialized")
    if not mini_batch:
        raise ValueError("mini_batch must contain at least one CSV path")
    outputs = []
    for source in mini_batch:
        frame = pd.read_csv(source, dtype={"customer_id": "string"})
        if frame.empty:
            continue
        outputs.append(
            score_frame(
                MODEL,
                frame,
                task_type=TASK_TYPE,
                source_file=Path(source).name,
            )
        )
    if not outputs:
        raise ValueError("No scoreable customer rows were found")
    return pd.concat(outputs, ignore_index=True)
