"""Static contracts for the reproducible non-root container."""

from pathlib import Path


def test_container_includes_customer_intelligence_runtime() -> None:
    dockerfile = Path("docker/Dockerfile").read_text(encoding="utf-8")

    assert "FROM python:3.11.9-slim-bookworm" in dockerfile
    assert "COPY --chown=mlops:mlops deployment ./deployment" in dockerfile
    assert "COPY --chown=mlops:mlops pipelines ./pipelines" in dockerfile
    assert "USER mlops" in dockerfile


def test_container_dependencies_pin_numeric_and_workbook_runtime() -> None:
    requirements = Path("requirements.txt").read_text(encoding="utf-8")

    assert "numpy==1.26.4" in requirements
    assert "openpyxl==3.1.5" in requirements
    assert "pandas==2.1.4" in requirements
