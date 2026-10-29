"""Tests for the reproducible training baseline."""

import json
from pathlib import Path

import mlflow.pyfunc
import pandas as pd
import pytest

from src.train import save_mlflow_model, train_from_paths, train_model


def test_train_model_produces_binary_predictions() -> None:
    features = pd.DataFrame(
        {
            "usage": [1.0, 1.5, 2.0, 8.0, 8.5, 9.0],
            "tenure": [2, 3, 4, 24, 30, 36],
        }
    )
    target = pd.Series([0, 0, 0, 1, 1, 1])

    model = train_model(features, target)
    predictions = model.predict(features)

    assert predictions.shape == (6,)
    assert set(predictions) <= {0, 1}


def test_train_model_handles_mixed_features_and_unknown_category() -> None:
    features = pd.DataFrame(
        {
            "age": [20, 30, 40, 50, 60, 70],
            "job": [
                "student",
                "admin",
                "admin",
                "retired",
                "retired",
                "student",
            ],
        }
    )
    target = pd.Series(["no", "no", "no", "yes", "yes", "yes"])
    model = train_model(features, target, class_weight="balanced")

    predictions = model.predict(pd.DataFrame({"age": [45], "job": ["unseen-job"]}))

    assert predictions.shape == (1,)
    assert predictions[0] in {"no", "yes"}


def test_train_model_requires_two_target_classes() -> None:
    features = pd.DataFrame({"age": [20, 30, 40]})
    target = pd.Series(["no", "no", "no"])

    with pytest.raises(ValueError, match="exactly two classes"):
        train_model(features, target)


def test_save_mlflow_model_preserves_existing_output_directory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    features = pd.DataFrame(
        {
            "usage": [1.0, 1.5, 2.0, 8.0, 8.5, 9.0],
            "tenure": [2, 3, 4, 24, 30, 36],
        }
    )
    target = pd.Series([0, 0, 0, 1, 1, 1])
    model = train_model(features, target)
    model_output = tmp_path / "mounted-output"
    model_output.mkdir()
    (model_output / "stale.txt").write_text("stale", encoding="utf-8")

    original_rmtree = __import__("shutil").rmtree

    def guarded_rmtree(path: str | Path, *args: object, **kwargs: object) -> None:
        if Path(path) == model_output:
            raise OSError("mounted output root must not be removed")
        original_rmtree(path, *args, **kwargs)

    monkeypatch.setattr("src.train.shutil.rmtree", guarded_rmtree)

    save_mlflow_model(model, features, model_output)

    assert model_output.is_dir()
    assert not (model_output / "stale.txt").exists()
    assert (model_output / "MLmodel").exists()


def test_train_from_paths_writes_loadable_mlflow_model(
    tmp_path: Path,
) -> None:
    training_path = tmp_path / "train.csv"
    model_output = tmp_path / "model"
    config_path = tmp_path / "config.json"
    pd.DataFrame(
        {
            "age": [20, 30, 40, 50, 60, 70],
            "job": [
                "student",
                "admin",
                "admin",
                "retired",
                "retired",
                "student",
            ],
            "y": ["no", "no", "no", "yes", "yes", "yes"],
        }
    ).to_csv(training_path, index=False)
    config_path.write_text(
        json.dumps(
            {
                "data": {
                    "target_column": "y",
                    "random_state": 42,
                },
                "training": {
                    "model_output": str(model_output),
                    "max_iter": 1000,
                    "regularization_strength": 1.0,
                    "class_weight": "balanced",
                },
            }
        ),
        encoding="utf-8",
    )

    metadata = train_from_paths(
        training_path,
        model_output,
        config_path,
    )
    loaded_model = mlflow.pyfunc.load_model(str(model_output))
    predictions = loaded_model.predict(pd.DataFrame({"age": [45], "job": ["admin"]}))

    assert (model_output / "MLmodel").exists()
    assert (model_output / "training_metadata.json").exists()
    assert metadata["features"]["categorical"] == ["job"]
    assert len(predictions) == 1
