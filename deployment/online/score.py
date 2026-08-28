"""Validated scoring entry point for an Azure ML managed online endpoint."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import mlflow.sklearn
import pandas as pd
from sklearn.pipeline import Pipeline

MODEL: Pipeline | None = None


def find_model_path(root: Path) -> Path:
    """Find the single MLflow model directory mounted by Azure ML."""
    candidates = [path.parent for path in root.rglob("MLmodel")]
    if len(candidates) != 1:
        raise ValueError(
            f"Expected exactly one MLflow model under {root}; found {len(candidates)}"
        )
    return candidates[0]


def init() -> None:
    """Load the deployed model once when the inference container starts."""
    global MODEL
    model_root = os.getenv("AZUREML_MODEL_DIR", "").strip()
    if not model_root:
        raise ValueError("AZUREML_MODEL_DIR is required")
    MODEL = mlflow.sklearn.load_model(str(find_model_path(Path(model_root))))


def parse_request(raw_data: str) -> pd.DataFrame:
    """Validate the endpoint request envelope and records."""
    try:
        payload = json.loads(raw_data)
    except json.JSONDecodeError as error:
        raise ValueError("Request body must be valid JSON") from error
    if not isinstance(payload, dict) or "input_data" not in payload:
        raise ValueError("Request must contain an input_data field")
    records = payload["input_data"]
    if not isinstance(records, list) or not records:
        raise ValueError("input_data must be a non-empty list of records")
    if not all(isinstance(record, dict) for record in records):
        raise ValueError("Every input_data item must be an object")
    frame = pd.DataFrame(records)
    if "duration" in frame.columns:
        raise ValueError("The prohibited duration feature must not be supplied")
    return frame


def run(raw_data: str) -> dict[str, Any]:
    """Return labels and positive-class probabilities for valid records."""
    if MODEL is None:
        raise RuntimeError("Model is not initialized")
    features = parse_request(raw_data)
    probabilities = MODEL.predict_proba(features)
    classes = list(MODEL.classes_)
    if "yes" not in classes:
        raise ValueError("Deployed model does not contain the positive class 'yes'")
    positive = probabilities[:, classes.index("yes")]
    predictions = MODEL.predict(features)
    return {
        "predictions": [str(value) for value in predictions],
        "probabilities": [float(value) for value in positive],
    }
