# Copilot Instructions

## Project Purpose

Develop a traceable end-to-end MLOps workflow that trains, evaluates, tracks, registers, tests, and packages machine-learning models for Azure Machine Learning.

## Tech Stack

- Python 3.11, pandas, scikit-learn, and pytest
- Azure Machine Learning with the `azure-ai-ml` SDK
- MLflow for experiment tracking and model artifacts
- Docker and GitHub Actions

## Coding Conventions

- Follow PEP 8, type public functions, and keep training, evaluation, registration, and pipeline orchestration separate.
- Give pipeline components verb-led snake_case names and MLflow runs descriptive names that distinguish baseline, tuning, and release candidates.
- Make every run reproducible with explicit seeds, dependency versions, input data references, and parameters.
- Pass configuration through function arguments, checked configuration files, or environment variables.
- Keep Docker build contexts small, pin production image versions when the scaffold becomes deployable, and run containers as a non-root user before production use.

## Learning Objectives to Reinforce

- **Experiment tracking:** log parameters, model evaluation metrics, dataset or asset references, source revision, and model artifacts for every meaningful MLflow run.
- **MLOps:** reinforce automated tests, CI gates, reproducible environments, model registration, lineage, promotion criteria, and rollback-friendly versioning.
- **Model evaluation metrics:** log more than accuracy; include precision, recall, F1, ROC-AUC, and threshold-specific measures appropriate to the use case.
- Connect traditional model-development decisions to operational outcomes such as latency, reproducibility, monitoring, and retraining.

## Work Breakdown and Documentation

- Organize the project as a traceable hierarchy:
  1. **Major project phases:** the top-level stages required to deliver the end-to-end MLOps workflow.
  2. **Overall steps:** the principal activities required to complete each major phase.
  3. **Granular tasks:** the specific, actionable implementation steps required to complete each overall step.
- Before implementation, identify where the work belongs in this hierarchy and preserve the relationship between each phase, step, and granular task.
- Maintain detailed documentation for every item at all three levels. At minimum, document:
  - what was done;
  - why it was necessary;
  - the important inputs, outputs, dependencies, and assumptions;
  - significant technical decisions and the alternatives or tradeoffs considered;
  - how the result was validated and how it contributes to the parent step and the end-to-end workflow.
- Keep the documentation current as implementation decisions change. Do not mark an item complete until its implementation and required documentation are both complete.
- Use explicit identifiers or links where practical so that granular tasks can be traced to their overall step, major phase, code changes, tests, pipeline runs, and resulting artifacts.

## Do

- Make pipeline steps idempotent and explicit about their inputs and outputs.
- Fail clearly when required configuration or artifacts are missing.
- Test deterministic local logic without requiring live Azure resources.
- Use `DefaultAzureCredential` and least-privilege managed identities for cloud authentication.

## Don't

- Never hardcode secrets, connection strings, subscription details, tokens, or credentials. Use environment variables, managed identity, GitHub OIDC, or Azure Key Vault references.
- Do not register a model without its evaluation metrics and provenance.
- Do not hide failed tracking or registration operations behind broad exception handlers.
- Do not couple unit tests to a live Azure ML workspace.
