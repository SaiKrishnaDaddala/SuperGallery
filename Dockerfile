FROM python:3.12-slim

# ffmpeg = video thumbnails
RUN apt-get update \
 && apt-get install -y --no-install-recommends ffmpeg \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY web ./web
COPY models ./models
COPY tools/download_models.py ./tools/download_models.py
RUN python tools/download_models.py

ENV SCAN_ROOTS=/nas \
    CONFIG_DIR=/config \
    PYTHONUNBUFFERED=1

EXPOSE 8800 8843
HEALTHCHECK --interval=60s --timeout=10s --start-period=30s \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8800/api/auth')"

# One worker on purpose: background indexing and the task queue live in this process.
CMD ["python", "-m", "app.serve"]
