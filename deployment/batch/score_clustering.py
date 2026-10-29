"""Azure ML batch entry point for customer clustering."""

import os

import pandas as pd

from deployment.batch import customer_intelligence_score


def init() -> None:
    """Initialize the shared scorer for clustering."""
    os.environ["CUSTOMER_INTELLIGENCE_TASK"] = "clustering"
    customer_intelligence_score.init()


def run(mini_batch: list[str]) -> pd.DataFrame:
    """Score a clustering mini-batch."""
    return customer_intelligence_score.run(mini_batch)
