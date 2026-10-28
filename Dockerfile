FROM python:3.12-slim

# Video thumbnails and probing use PyAV (FFmpeg libraries in a ~35 MB wheel) instead of Debian's ffmpeg.
# The optional Amazon Rekognition celebrity lookup needs boto3: build with --build-arg WITH_AWS=1.
ARG WITH_AWS=0
WORKDIR /app
COPY requirements.txt requirements-aws.txt ./
RUN pip install --no-cache-dir -r requirements.txt \
 && if [ "$WITH_AWS" = "1" ]; then pip install --no-cache-dir -r requirements-aws.txt; fi

COPY LICENSE NOTICE THIRD_PARTY_NOTICES.md ./
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
