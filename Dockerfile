# syntax=docker/dockerfile:1
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    ADA_VIEWER_HOST=0.0.0.0 \
    ADA_VIEWER_PORT=8080 \
    ADA_VIEWER_MAX_UPLOAD_MB=100 \
    ADA_HDF5_ROOTS=/data \
    ADA_VIEWER_UPLOAD_DIR=/tmp/tofshield/uploads \
    ADA_VIEWER_GENERATED_DIR=/tmp/tofshield/generated

WORKDIR /app

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./
RUN mkdir -p /data /tmp/tofshield/uploads /tmp/tofshield/generated \
    && useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /data /tmp/tofshield

USER appuser
EXPOSE 8080

CMD ["gunicorn", "--bind", "0.0.0.0:8080", "--workers", "1", "--threads", "4", "--timeout", "300", "--access-logfile", "-", "server:app"]
