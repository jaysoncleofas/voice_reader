# ---- builder: compiles the few dependencies that ship no arm64 wheels ----
FROM python:3.12-slim AS builder

# monotonic-alignment-search (a coqui-tts dependency) is a C extension with no
# prebuilt aarch64 wheel, so it is compiled here. The toolchain stays in this
# stage and never reaches the runtime image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PIP_NO_CACHE_DIR=1
RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# coqui-tts declares torch only under its 'cpu'/'cuda' extras, so torch is
# pinned explicitly. The CPU index keeps x86 builds from pulling CUDA payloads;
# on arm64 the wheels are CPU-only regardless.
COPY requirements.txt .
RUN pip install --upgrade pip setuptools wheel \
    && pip install --extra-index-url https://download.pytorch.org/whl/cpu -r requirements.txt


# ---- runtime ----
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/srv \
    PATH="/opt/venv/bin:$PATH" \
    VOICE_DATA_DIR=/data \
    # Model weights and the clip cache live on the volume, not in the image,
    # so a rebuild never re-downloads the ~1.8GB checkpoint.
    TTS_HOME=/data/models \
    XDG_DATA_HOME=/data/models \
    # XTTS-v2 ships under the Coqui Public Model License; acknowledging it here
    # keeps the loader from blocking on an interactive prompt.
    COQUI_TOS_AGREED=1

# ffmpeg normalises browser recordings into the mono PCM the model expects.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv

WORKDIR /srv
COPY app ./app

VOLUME ["/data"]
EXPOSE 8080

CMD ["python", "-m", "app.main"]
