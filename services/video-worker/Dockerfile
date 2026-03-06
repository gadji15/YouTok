FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        curl \
        ffmpeg \
        gcc g++ \
        libglib2.0-0 \
        libgl1 \
        libva2 \
        vainfo \
        mesa-va-drivers \
        i965-va-driver \
        fonts-dejavu-core \
        fonts-noto-core \
        fonts-noto-color-emoji \
        tesseract-ocr \
        tesseract-ocr-eng \
        tesseract-ocr-fra \
        tesseract-ocr-ara \
    && rm -rf /var/lib/apt/lists/*

ARG PYTORCH_EXTRA_INDEX_URL=https://download.pytorch.org/whl/cpu

ENV PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DEFAULT_TIMEOUT=120 \
    PIP_EXTRA_INDEX_URL=${PYTORCH_EXTRA_INDEX_URL}

# Note: Whisper (and torch wheels) are heavy; keep them in earlier layers so
# changes to app deps don't force reinstalling torch.
COPY requirements-whisper.txt ./requirements-whisper.txt
RUN pip install --no-cache-dir --prefer-binary -r requirements-whisper.txt

# WhisperX is heavy; we only install it on amd64 by default.
#
# MediaPipe does not provide wheels for all architectures; face detection is
# best-effort and the pipeline still works without it.
COPY requirements-align.txt ./requirements-align.txt
COPY requirements-cv.txt ./requirements-cv.txt
COPY requirements-ocr.txt ./requirements-ocr.txt
ARG TARGETARCH
RUN if [ -z "$TARGETARCH" ] || [ "$TARGETARCH" = "amd64" ]; then pip install --no-cache-dir --prefer-binary -r requirements-align.txt -r requirements-cv.txt -r requirements-ocr.txt; fi

COPY requirements.txt ./requirements.txt
RUN pip install --no-cache-dir --prefer-binary -r requirements.txt

# Dev-only deps (used by CI / dockerized test runs)
COPY requirements-dev.txt ./requirements-dev.txt
RUN pip install --no-cache-dir --prefer-binary -r requirements-dev.txt

COPY video_worker ./video_worker
COPY tests ./tests

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "video_worker.api:app", "--host=0.0.0.0", "--port=8000"]
