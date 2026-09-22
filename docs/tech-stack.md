# Tech stack

Decisions are deliberate. Alternatives are listed so future changes are cheap.

## Runtime

| Piece | Choice | Why |
|---|---|---|
| Ingest pipeline | Python 3.12 | Media/ML ecosystem: ffmpeg bindings, faster-whisper, ONNX, PySceneDetect |
| API | FastAPI | One process serves REST and the MCP server; typed schemas for tools |
| Web | Next.js + TypeScript + Tailwind | Fast to build, good video-player ergonomics, deploys on Vercel |
| Package managers | uv (Python), pnpm (web) | Speed, lockfile discipline |

## Media

- FFmpeg for probe, proxy transcode, thumbnail extraction, audio extraction.
- NVENC when an NVIDIA GPU is present; x264 fallback for CPU-only runs.
- PySceneDetect for shot boundaries.

## ML (inference only — no training in v1)

- **Embeddings:** two spaces (ADR-0003). SigLIP-base for frames and visual queries, exported to ONNX, int8 quantized, CPU runtime; bge-small-en-v1.5 for transcript segments and transcript queries, same export path. Within each space, index and query vectors use one model and one precision.
- **ASR:** faster-whisper, large-v3, int8. CUDA when available; CPU fallback.
- **Rerank (optional):** cross-encoder or multimodal LLM over top-k. Off by default until the eval justifies it.
- **GPU policy:** optional accelerator. ASR and proxy encode are the wins. CPU-only runs must stay correct and publishable.

## Storage

- **Vectors + metadata:** LanceDB (embedded ANN, no service to run).
- **Thumbnails:** JPEG on disk, served statically.
- **Artifacts:** per-asset directory under `work/`, manifests as JSON.
- **Transcripts:** per-asset JSON with word timestamps; range reads via the index.

## Eval

- `eval/queries.yaml` — labeled queries with splits and expected ranges.
- Harness in Python. Metrics: Recall@5, MRR, p50/p95 query latency.
- Baseline: single-stage CLIP retrieval, same corpus, same sampling.
- Results committed as markdown tables.

## Infra

- Local: docker-compose.
- Demo: Fly.io (API, 1 shared CPU / 1 GB) + Vercel (web). Budget target ≤ $10/month.
- Demo media: playback proxies packed as a GitHub release asset and fetched into `index/` at image build (ADR-0004).
- CI: GitHub Actions (lint, unit tests, fixture ingest smoke test).

## Rejected for v1

- Queue/broker (Redis, Celery): a stage cache plus `--workers N` covers a single machine. Revisit for live uploads.
- Managed vector DB: adds a service without adding capability at this scale.
- Rust/Go: no hot path that Python + ONNX cannot hold. Revisit only if benchmarks say otherwise.
