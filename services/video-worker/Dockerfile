FROM python:3.11-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        gcc g++ \
        libglib2.0-0 \
        libgl1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./requirements.txt
COPY requirements-whisper.txt ./requirements-whisper.txt
COPY requirements-align.txt ./requirements-align.txt
COPY requirements-cv.txt ./requirements-cv.txt

# Note: Whisper (and torch wheels) are heavy; kept separate so contributors can
# run unit tests without pulling ML wheels.
#
# WhisperX is also heavy; we only install it on amd64 by default.
#
# MediaPipe does not provide wheels for all architectures; face detection is
# best-effort and the pipeline still works without it.
ARG TARGETARCH
RUN pip install --no-cache-dir -r requirements.txt -r requirements-whisper.txt \
    && if [ -z "$TARGETARCH" ] || [ "$TARGETARCH" = "amd64" ]; then pip install --no-cache-dir -r requirements-align.txt -r requirements-cv.txt; fi

COPY video_worker ./video_worker

ENV PYTHONUNBUFFERED=1

CMD ["uvicorn", "video_worker.api:app", "--host=0.0.0.0", "--port=8000"]
