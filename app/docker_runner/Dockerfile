# ─── Benchmark Worker Dockerfile ─────────────────────────────────────────────
# Lightweight image for running ML model benchmarks in isolation
# This container runs untrusted user models safely

FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# Install only the essential ML libraries
RUN pip install --no-cache-dir \
    scikit-learn==1.3.2 \
    numpy==1.26.2 \
    pandas==2.1.4 \
    joblib==1.3.2 \
    psutil==5.9.6 \
    onnxruntime==1.16.3 \
    xgboost==2.0.3 \
    lightgbm==4.1.0

# Copy the worker script
COPY app/docker_runner/worker.py .

# Run with minimal privileges
USER nobody

# The worker reads environment variables:
# MODEL_PATH, FRAMEWORK, DATASET_NAME, TASK_TYPE
CMD ["python", "worker.py"]
