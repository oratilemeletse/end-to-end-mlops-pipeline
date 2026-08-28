FROM python:3.11.9-slim-bookworm

ARG PIP_INDEX_URL=https://pypi.org/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    GIT_PYTHON_REFRESH=quiet

WORKDIR /app

COPY requirements.txt .
RUN python -m pip install \
    --no-cache-dir \
    --retries 10 \
    --timeout 60 \
    --index-url "${PIP_INDEX_URL}" \
    -r requirements.txt

RUN addgroup --system mlops \
    && adduser --system --ingroup mlops --home /home/mlops mlops \
    && mkdir -p /app/artifacts /app/data/raw \
    && chown -R mlops:mlops /app /home/mlops

COPY --chown=mlops:mlops configs ./configs
COPY --chown=mlops:mlops src ./src
COPY --chown=mlops:mlops pipelines ./pipelines
COPY --chown=mlops:mlops scripts ./scripts

USER mlops

CMD ["python", "-m", "pipelines.run_local", "--config", "configs/local.json"]
