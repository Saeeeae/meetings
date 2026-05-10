FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

ARG INSTALL_ML=false
ARG INSTALL_VLLM=false

COPY requirements.txt requirements-ml.txt requirements-vllm.txt ./
RUN if [ "$INSTALL_VLLM" = "true" ]; then \
      pip install --no-cache-dir -r requirements-vllm.txt; \
    elif [ "$INSTALL_ML" = "true" ]; then \
      pip install --no-cache-dir -r requirements-ml.txt; \
    else \
      pip install --no-cache-dir -r requirements.txt; \
    fi

COPY app ./app
COPY scripts ./scripts

RUN chmod +x /app/scripts/download_models.py
