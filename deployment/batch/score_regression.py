"""Azure ML batch entry point for customer spending regression."""

import os

import pandas as pd

from deployment.batch import customer_intelligence_score


def init() -> None:
    """Initialize the shared scorer for regression."""
    os.environ["CUSTOMER_INTELLIGENCE_TASK"] = "regression"
    customer_intelligence_score.init()


def run(mini_batch: list[str]) -> pd.DataFrame:
    """Score a regression mini-batch."""
    return customer_intelligence_score.run(mini_batch)
