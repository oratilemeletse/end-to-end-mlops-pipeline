"""Train and evaluate deterministic RFM customer segmentation."""

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
from sklearn.cluster import KMeans
from sklearn.impute import SimpleImputer
from sklearn.metrics import (
    adjusted_rand_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import PowerTransformer

from src.customer_intelligence_data import (
    CLUSTERING_FEATURES,
    IDENTIFIER_COLUMNS,
    load_retail_config,
)
from src.prepare_data import sha256
from src.train import save_mlflow_model


@dataclass(frozen=True)
class ClusteringConfig:
    """Validated segmentation model and release settings."""

    model_output: Path
    evaluation_output: Path
    candidate_clusters: tuple[int, ...]
    silhouette_sample_size: int
    stability_runs: int
    minimum_silhouette: float
    maximum_davies_bouldin: float
    minimum_cluster_fraction: float
    minimum_stability: float
    random_state: int


def load_clustering_config(path: Path) -> ClusteringConfig:
    """Load and validate clustering settings."""
    if not path.exists():
        raise FileNotFoundError(f"Configuration file does not exist: {path}")
    raw = json.loads(path.read_text(encoding="utf-8"))
    retail = load_retail_config(path)
    try:
        settings = raw["clustering"]
        config = ClusteringConfig(
            model_output=Path(settings["model_output"]),
            evaluation_output=Path(settings["evaluation_output"]),
            candidate_clusters=tuple(
                int(value) for value in settings["candidate_clusters"]
            ),
            silhouette_sample_size=int(settings["silhouette_sample_size"]),
            stability_runs=int(settings["stability_runs"]),
            minimum_silhouette=float(settings["minimum_silhouette"]),
            maximum_davies_bouldin=float(settings["maximum_davies_bouldin"]),
            minimum_cluster_fraction=float(settings["minimum_cluster_fraction"]),
            minimum_stability=float(settings["minimum_stability"]),
            random_state=retail.random_state,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid clustering configuration in {path}: {error}"
        ) from error
    if not config.candidate_clusters or any(
        value < 2 for value in config.candidate_clusters
    ):
        raise ValueError("clustering.candidate_clusters must contain values >= 2")
    if len(set(config.candidate_clusters)) != len(config.candidate_clusters):
        raise ValueError("clustering.candidate_clusters must be unique")
    if config.silhouette_sample_size < 2:
        raise ValueError("clustering.silhouette_sample_size must be at least two")
    if config.stability_runs < 2:
        raise ValueError("clustering.stability_runs must be at least two")
    if not -1 <= config.minimum_silhouette <= 1:
        raise ValueError("clustering.minimum_silhouette must be between -1 and 1")
    if config.maximum_davies_bouldin <= 0:
        raise ValueError("clustering.maximum_davies_bouldin must be positive")
    for name, value in {
        "minimum_cluster_fraction": config.minimum_cluster_fraction,
        "minimum_stability": config.minimum_stability,
    }.items():
        if not 0 <= value <= 1:
            raise ValueError(f"clustering.{name} must be between zero and one")
    return config


def validate_clustering_data(data: pd.DataFrame) -> None:
    """Validate the prepared clustering snapshot."""
    required = set(IDENTIFIER_COLUMNS + CLUSTERING_FEATURES)
    missing = required.difference(data.columns)
    if missing:
        raise ValueError(
            "Clustering data is missing required columns: " + ", ".join(sorted(missing))
        )
    if data.empty:
        raise ValueError("Clustering data must contain at least one row")
    values = data[CLUSTERING_FEATURES].to_numpy(dtype=float)
    if not np.isfinite(values).all():
        raise ValueError("Clustering data contains non-finite values")
    if (values < 0).any():
        raise ValueError("RFM clustering features must not be negative")


def build_clustering_model(
    cluster_count: int,
    *,
    random_state: int,
) -> Pipeline:
    """Construct a seeded K-means pipeline."""
    if cluster_count < 2:
        raise ValueError("cluster_count must be at least two")
    return Pipeline(
        [
            ("impute", SimpleImputer(strategy="median")),
            (
                "transform",
                PowerTransformer(method="yeo-johnson", standardize=True),
            ),
            (
                "cluster",
                KMeans(
                    n_clusters=cluster_count,
                    random_state=random_state,
                    n_init=20,
                ),
            ),
        ]
    )


def clustering_metrics(
    model: Pipeline,
    features: pd.DataFrame,
    *,
    sample_size: int,
    random_state: int,
) -> dict[str, float]:
    """Calculate permutation-invariant internal clustering metrics."""
    labels = np.asarray(model.predict(features), dtype=int)
    unique, counts = np.unique(labels, return_counts=True)
    if unique.size < 2:
        raise ValueError("Clustering produced fewer than two populated clusters")
    transformed = np.asarray(model[:-1].transform(features), dtype=float)
    if len(features) > sample_size:
        random = np.random.default_rng(random_state)
        sample_indices = np.sort(
            random.choice(len(features), size=sample_size, replace=False)
        )
    else:
        sample_indices = np.arange(len(features))
    sampled_labels = labels[sample_indices]
    if np.unique(sampled_labels).size < 2:
        raise ValueError("Silhouette sample contains fewer than two clusters")
    return {
        "silhouette_score": float(
            silhouette_score(
                transformed[sample_indices],
                sampled_labels,
            )
        ),
        "davies_bouldin_score": float(davies_bouldin_score(transformed, labels)),
        "minimum_cluster_fraction": float(counts.min() / counts.sum()),
    }


def clustering_stability(
    features: pd.DataFrame,
    *,
    cluster_count: int,
    random_state: int,
    runs: int,
) -> float:
    """Compare seeded refits with adjusted Rand index."""
    reference = build_clustering_model(
        cluster_count,
        random_state=random_state,
    ).fit_predict(features)
    scores = []
    for offset in range(1, runs):
        comparison = build_clustering_model(
            cluster_count,
            random_state=random_state + offset,
        ).fit_predict(features)
        scores.append(float(adjusted_rand_score(reference, comparison)))
    return float(np.mean(scores))


def train_clustering_from_paths(
    prepared_data: Path,
    model_output: Path,
    config_path: Path,
) -> dict[str, Any]:
    """Select, fit, and persist a customer-segmentation model."""
    config = load_clustering_config(config_path)
    data_path = (
        prepared_data / "clustering.csv" if prepared_data.is_dir() else prepared_data
    )
    if not data_path.exists():
        raise FileNotFoundError(f"Clustering data does not exist: {data_path}")
    data = pd.read_csv(data_path, dtype={"customer_id": "string"})
    validate_clustering_data(data)
    features = data[CLUSTERING_FEATURES].astype(float)
    largest_candidate = max(config.candidate_clusters)
    if len(features) <= largest_candidate:
        raise ValueError("Clustering data must outnumber every candidate cluster count")

    candidates: dict[str, dict[str, float]] = {}
    for cluster_count in config.candidate_clusters:
        model = build_clustering_model(
            cluster_count,
            random_state=config.random_state,
        )
        model.fit(features)
        metrics = clustering_metrics(
            model,
            features,
            sample_size=config.silhouette_sample_size,
            random_state=config.random_state,
        )
        metrics["stability_score"] = clustering_stability(
            features,
            cluster_count=cluster_count,
            random_state=config.random_state,
            runs=config.stability_runs,
        )
        candidates[str(cluster_count)] = metrics
    selected_cluster_count = int(
        max(
            candidates,
            key=lambda value: candidates[value]["silhouette_score"],
        )
    )
    model = build_clustering_model(
        selected_cluster_count,
        random_state=config.random_state,
    )
    model.fit(features)
    save_mlflow_model(model, features, model_output)
    metadata: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "task_id": "CI-C.1.1",
        "task_type": "clustering",
        "training_data": {
            "path": str(data_path),
            "sha256": sha256(data_path),
            "rows": len(data),
        },
        "feature_columns": CLUSTERING_FEATURES,
        "parameters": {
            "algorithm": "kmeans",
            "candidate_clusters": list(config.candidate_clusters),
            "selected_clusters": selected_cluster_count,
            "random_state": config.random_state,
            "n_init": 20,
            "silhouette_sample_size": config.silhouette_sample_size,
            "stability_runs": config.stability_runs,
        },
        "candidate_metrics": candidates,
        "model_output": str(model_output),
        "format": "mlflow_model",
    }
    (model_output / "training_metadata.json").write_text(
        json.dumps(metadata, indent=2) + "\n",
        encoding="utf-8",
    )
    return metadata


def cluster_profiles(
    data: pd.DataFrame,
    labels: np.ndarray,
    distances: np.ndarray,
) -> list[dict[str, Any]]:
    """Build version-local, reviewable RFM summaries for each cluster."""
    profiled = data[["customer_id", *CLUSTERING_FEATURES]].copy()
    profiled["cluster_id"] = labels
    profiled["distance_to_centroid"] = distances
    profiles: list[dict[str, Any]] = []
    for cluster_id, cluster in profiled.groupby("cluster_id", sort=True):
        profiles.append(
            {
                "cluster_id": int(cluster_id),
                "customers": int(len(cluster)),
                "customer_fraction": float(len(cluster) / len(profiled)),
                "feature_means": {
                    feature: float(cluster[feature].mean())
                    for feature in CLUSTERING_FEATURES
                },
                "feature_medians": {
                    feature: float(cluster[feature].median())
                    for feature in CLUSTERING_FEATURES
                },
                "mean_distance_to_centroid": float(
                    cluster["distance_to_centroid"].mean()
                ),
                "business_label": None,
                "review_required": True,
            }
        )
    return profiles


def evaluate_clustering_from_paths(
    model_path: Path,
    prepared_data: Path,
    config_path: Path,
    output_dir: Path | None = None,
) -> dict[str, Any]:
    """Evaluate cluster validity, stability, sizes, and profiles."""
    config = load_clustering_config(config_path)
    data_path = (
        prepared_data / "clustering.csv" if prepared_data.is_dir() else prepared_data
    )
    if not model_path.exists():
        raise FileNotFoundError(f"Clustering model does not exist: {model_path}")
    if not data_path.exists():
        raise FileNotFoundError(f"Clustering data does not exist: {data_path}")
    metadata_path = model_path / "training_metadata.json"
    if not metadata_path.exists():
        raise FileNotFoundError(f"Clustering metadata does not exist: {metadata_path}")
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    data = pd.read_csv(data_path, dtype={"customer_id": "string"})
    validate_clustering_data(data)
    features = data[CLUSTERING_FEATURES].astype(float)
    model = mlflow.sklearn.load_model(str(model_path))
    labels = np.asarray(model.predict(features), dtype=int)
    distances = np.asarray(model.transform(features), dtype=float).min(axis=1)
    metrics = clustering_metrics(
        model,
        features,
        sample_size=config.silhouette_sample_size,
        random_state=config.random_state,
    )
    selected_clusters = str(metadata["parameters"]["selected_clusters"])
    metrics["stability_score"] = float(
        metadata["candidate_metrics"][selected_clusters]["stability_score"]
    )
    metrics["mean_distance_to_centroid"] = float(distances.mean())
    checks = {
        "silhouette": metrics["silhouette_score"] >= config.minimum_silhouette,
        "davies_bouldin": (
            metrics["davies_bouldin_score"] <= config.maximum_davies_bouldin
        ),
        "cluster_size": (
            metrics["minimum_cluster_fraction"] >= config.minimum_cluster_fraction
        ),
        "stability": metrics["stability_score"] >= config.minimum_stability,
    }
    profiles = cluster_profiles(data, labels, distances)
    destination = output_dir or config.evaluation_output
    destination.mkdir(parents=True, exist_ok=True)
    assignments = data[IDENTIFIER_COLUMNS].copy()
    assignments["cluster_id"] = labels
    assignments["distance_to_centroid"] = distances
    assignments.to_csv(destination / "assignments.csv", index=False)
    report: dict[str, Any] = {
        "created_at": datetime.now(UTC).isoformat(),
        "task_id": "CI-C.1.2",
        "task_type": "clustering",
        "model_path": str(model_path),
        "data_path": str(data_path),
        "rows": len(data),
        "feature_columns": CLUSTERING_FEATURES,
        "metrics": metrics,
        "cluster_profiles": profiles,
        "thresholds": {
            "minimum_silhouette": config.minimum_silhouette,
            "maximum_davies_bouldin": config.maximum_davies_bouldin,
            "minimum_cluster_fraction": config.minimum_cluster_fraction,
            "minimum_stability": config.minimum_stability,
        },
        "threshold_checks": checks,
        "approved": all(checks.values()),
        "limitations": [
            "Internal clustering metrics do not establish business value.",
            "Cluster identifiers are local to this model version.",
            "Business segment labels require profile review before operational use.",
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
    (destination / "cluster_profiles.json").write_text(
        json.dumps(profiles, indent=2) + "\n",
        encoding="utf-8",
    )
    return report


def parse_train_args() -> argparse.Namespace:
    """Parse clustering training arguments."""
    parser = argparse.ArgumentParser(description="Train retail customer clustering.")
    parser.add_argument(
        "--prepared-data",
        type=Path,
        default=Path("artifacts/customer_intelligence/prepared"),
    )
    parser.add_argument("--model-output", type=Path, default=None)
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("configs/customer_intelligence.json"),
    )
    return parser.parse_args()


def parse_evaluate_args() -> argparse.Namespace:
    """Parse clustering evaluation arguments."""
    parser = argparse.ArgumentParser(description="Evaluate customer clustering.")
    parser.add_argument(
        "--model-input",
        type=Path,
        default=Path("artifacts/customer_intelligence/model/customer-segmentation"),
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
    """Run clustering training."""
    args = parse_train_args()
    config = load_clustering_config(args.config)
    metadata = train_clustering_from_paths(
        args.prepared_data,
        args.model_output or config.model_output,
        args.config,
    )
    print(
        f"Clustering training complete: k={metadata['parameters']['selected_clusters']}"
    )


def evaluate_main() -> None:
    """Run clustering evaluation."""
    args = parse_evaluate_args()
    report = evaluate_clustering_from_paths(
        args.model_input,
        args.prepared_data,
        args.config,
        args.evaluation_output,
    )
    print(
        "Clustering evaluation complete: "
        f"silhouette={report['metrics']['silhouette_score']:.4f}, "
        f"approved={report['approved']}"
    )
