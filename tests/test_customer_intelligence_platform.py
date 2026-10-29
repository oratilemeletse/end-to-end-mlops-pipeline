"""Tests for task-aware tracking, release, and scoring contracts."""

from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from sklearn.cluster import KMeans
from sklearn.linear_model import LinearRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from deployment.batch.customer_intelligence_score import score_frame
from pipelines.run_customer_intelligence import flatten_mapping
from src.customer_intelligence_data import CLUSTERING_FEATURES, REGRESSION_FEATURES
from src.customer_intelligence_release import build_release_evidence


def test_flatten_mapping_preserves_nested_parameters() -> None:
    flattened = flatten_mapping(
        {"model": {"name": "ridge", "values": [1, 2]}, "seed": 42}
    )

    assert flattened == {
        "model.name": "ridge",
        "model.values": "[1, 2]",
        "seed": 42,
    }


def test_release_evidence_rejects_task_mismatch(tmp_path: Path) -> None:
    report = {"task_type": "regression", "approved": True, "metrics": {}}
    training = {"task_type": "clustering"}

    with pytest.raises(ValueError, match="Training metadata task"):
        build_release_evidence(
            task_type="regression",
            report=report,
            training_metadata=training,
            preparation_metadata={"source": {"sha256": "abc"}, "task_ids": []},
            run_id="run",
            source_revision="revision",
            source_dirty=False,
            dependency_versions={},
            model_artifact_uri="runs:/run/model",
            configuration_path=tmp_path / "config.json",
        )


def test_regression_batch_scoring_clips_negative_predictions() -> None:
    features = pd.DataFrame(
        {feature: [1.0, 2.0, 3.0] for feature in REGRESSION_FEATURES}
    )
    target = np.array([-1.0, -2.0, -3.0])
    model = Pipeline([("regressor", LinearRegression())]).fit(features, target)
    frame = features.copy()
    frame["customer_id"] = ["1", "2", "3"]

    result = score_frame(
        model,
        frame,
        task_type="regression",
        source_file="customers.csv",
    )

    assert (result["predicted_spend_gbp"] == 0).all()
    assert result["customer_id"].tolist() == ["1", "2", "3"]


def test_clustering_batch_scoring_returns_version_local_clusters() -> None:
    features = pd.DataFrame(
        {
            "recency_days": [1.0, 2.0, 80.0, 90.0],
            "purchase_invoices": [10.0, 12.0, 1.0, 2.0],
            "monetary_value_gbp": [500.0, 600.0, 10.0, 20.0],
        }
    )
    model = Pipeline(
        [
            ("scale", StandardScaler()),
            ("cluster", KMeans(n_clusters=2, random_state=42, n_init=10)),
        ]
    ).fit(features[CLUSTERING_FEATURES])
    frame = features.copy()
    frame["customer_id"] = ["1", "2", "3", "4"]

    result = score_frame(
        model,
        frame,
        task_type="clustering",
        source_file="customers.csv",
    )

    assert set(result["cluster_id"]) == {0, 1}
    assert (result["distance_to_centroid"] >= 0).all()
