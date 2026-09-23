# The demo API image: one process serves REST, MCP, thumbnails, and playback.
#
# The committed index/ carries search tables, transcripts, and thumbnails; the
# playback proxies are fetched from the demo-media-v4 GitHub release at build
# time (set SHOTGREP_DEMO_MEDIA_URL to override, or rebuild with `--no-cache`
# after a repack). Query embeddings run on the CPU with the pinned ONNX models
# baked into the image, so the first search does not wait on Hugging Face.

FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim

# OpenCV (pulled in by PySceneDetect) needs libGL even for the read-only API.
RUN apt-get update \
    && apt-get install -y --no-install-recommends libgl1 libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HOME=/models

WORKDIR /app

COPY pyproject.toml uv.lock README.md ./
RUN uv sync --frozen --no-install-project --no-dev

COPY pipeline ./pipeline
COPY api ./api
RUN uv sync --frozen --no-dev

RUN uv run --no-sync python -c "from pipeline.models.embedder import SiglipOnnxEmbedder; from pipeline.models.text_embedder import TextOnnxEmbedder; SiglipOnnxEmbedder().embed_text('warmup'); TextOnnxEmbedder().embed_query('warmup')"

COPY index ./index
COPY scripts ./scripts
ARG SHOTGREP_DEMO_MEDIA_URL=""
ENV SHOTGREP_DEMO_MEDIA_URL=${SHOTGREP_DEMO_MEDIA_URL}
RUN python3 scripts/demo_media.py fetch --optional

ENV SHOTGREP_API_URL=http://localhost:8080 \
    SHOTGREP_WEB_URL=http://localhost:3000

EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=20s \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/health', timeout=3)"

CMD ["uv", "run", "--no-sync", "shotgrep", "serve", "--work-dir", ".", "--host", "0.0.0.0", "--port", "8080"]
