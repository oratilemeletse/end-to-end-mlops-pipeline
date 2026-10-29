"""Tests for RFM customer clustering."""

import pandas as pd
import pytest

from src.customer_intelligence_clustering import (
    build_clustering_model,
    cluster_profiles,
    clustering_metrics,
    clustering_stability,
    validate_clustering_data,
)
from src.customer_intelligence_data import CLUSTERING_FEATURES


def clustering_frame() -> pd.DataFrame:
    """Return two clearly separated RFM groups."""
    return pd.DataFrame(
        {
            "customer_id": [str(value) for value in range(1, 9)],
            "cutoff_date": ["2024-01-01"] * 8,
            "target_window_end": ["2024-02-01"] * 8,
            "recency_days": [2, 3, 4, 5, 70, 75, 80, 85],
            "purchase_invoices": [20, 22, 18, 21, 1, 2, 1, 2],
            "monetary_value_gbp": [900, 1000, 850, 950, 10, 20, 15, 25],
        }
    )


def test_cluster_metrics_and_stability_are_deterministic() -> None:
    frame = clustering_frame()
    features = frame[CLUSTERING_FEATURES]
    model = build_clustering_model(2, random_state=42).fit(features)

    first = clustering_metrics(
        model,
        features,
        sample_size=8,
        random_state=42,
    )
    second = clustering_metrics(
        model,
        features,
        sample_size=8,
        random_state=42,
    )
    stability = clustering_stability(
        features,
        cluster_count=2,
        random_state=42,
        runs=3,
    )

    assert first == second
    assert first["silhouette_score"] > 0.8
    assert stability == pytest.approx(1.0)


def test_profiles_do_not_assign_unreviewed_business_labels() -> None:
    frame = clustering_frame()
    features = frame[CLUSTERING_FEATURES]
    model = build_clustering_model(2, random_state=42).fit(features)
    labels = model.predict(features)
    distances = model.transform(features).min(axis=1)

    profiles = cluster_profiles(frame, labels, distances)

    assert len(profiles) == 2
    assert all(profile["business_label"] is None for profile in profiles)
    assert all(profile["review_required"] is True for profile in profiles)


def test_clustering_data_rejects_negative_rfm_values() -> None:
    frame = clustering_frame()
    frame.loc[0, "monetary_value_gbp"] = -1

    with pytest.raises(ValueError, match="must not be negative"):
        validate_clustering_data(frame)


def test_clustering_model_requires_two_clusters() -> None:
    with pytest.raises(ValueError, match="at least two"):
        build_clustering_model(1, random_state=42)
