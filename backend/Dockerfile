FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

ARG PYTORCH_CPU_INDEX_URL=https://download.pytorch.org/whl/cpu

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN python -m pip install --upgrade pip && \
    python -m pip install --index-url "${PYTORCH_CPU_INDEX_URL}" torch==2.8.0 && \
    python -m pip install -r requirements.txt

RUN apt-get update && \
    apt-get install --no-install-recommends --yes libgomp1 && \
    rm -rf /var/lib/apt/lists/*

COPY backend/app ./app
COPY backend/alembic.ini ./alembic.ini
COPY backend/alembic ./alembic
COPY data/samples/extraction /data/samples/extraction

RUN useradd --create-home --uid 10001 appuser && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
