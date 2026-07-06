FROM python:3.12-slim
WORKDIR /app
# System libs for audio decoding. The worker analyses browser recordings (.webm/Opus)
# with librosa, which needs ffmpeg to decode non-WAV formats (without it: audioread
# NoBackendError). libsndfile1 covers WAV/FLAC via soundfile.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
    && rm -rf /var/lib/apt/lists/*
# Install from requirements.txt so declared deps (parselmouth, psycopg2, boto3, …)
# are not silently dropped by a hand-maintained package list.
COPY requirements.txt ./
RUN pip install --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt
COPY app ./app
# Alembic config + full migration set (schema, RLS, roles, grants, seeds), so
# `alembic upgrade head` can run inside the container. Single source of truth,
# shared with the dev setup (bbdd_dev_setup/up.sh points here too).
COPY db-migrations ./db-migrations
EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
