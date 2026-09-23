# shotgrep

Search video like it's text.

Ask for a moment in plain language — *"the part where he parks the bike at night"* — and get the exact frame back, with jump-to-timestamp links.

**Measured** on four Blender open films (47.9 min, 3,797 moments) against 64
frozen queries — full tables in [eval/RESULTS.md](eval/RESULTS.md), failure
analysis in [eval/ANALYSIS.md](eval/ANALYSIS.md):

| Metric | fused search | visual baseline |
|---|---|---|
| Recall@5 | **0.688** | 0.578 |
| MRR | **0.495** | 0.420 |
| Latency at k=10 | **p50 189 ms · p95 234 ms** | p50 54 ms · p95 75 ms |

Ingest is measured, not estimated: a [recorded run](docs/demo/ingest.md) takes
an arbitrary 60 s 1080p clip from file to searchable index in 72 s (0.83×
realtime, ASR on CUDA), with every stage's wall clock in
[the timings file](docs/demo/ingest.timings.json).

## Demo

**Live:** <https://shotgrep-demo.vercel.app> — instant search over the prebuilt
corpus (API on Fly.io at <https://shotgrep-demo.fly.dev>, agent tools at `/mcp`).

The repository ships the same prebuilt corpus index in `index/`, so search works
from a checkout with no ingest:

```sh
uv sync
uv run shotgrep serve --work-dir .        # REST + MCP on http://localhost:8000
python3 scripts/demo_media.py fetch       # playback proxies from the demo-media release
cd web && pnpm install && pnpm dev        # player on http://localhost:3000
```

Or one command with Docker:

```sh
docker compose up --build                 # API on :8000, web on :3000
```

The hosted demo (API on Fly.io, web on Vercel) deploys from this commit; the
full runbook is [docs/deploy.md](docs/deploy.md).

## How it works

```
        OFFLINE (batch, one machine)                ONLINE (served)
┌──────────────────────────────────────┐   ┌──────────────────────────────┐
│ asset → probe → proxy → shots        │   │ query → embed → ANN → fuse   │
│       → asr → frames → embed →       │──▶│       → dedupe → results     │
│       index write → manifest         │   │            │                 │
└──────────────────────────────────────┘   │     ┌──────┴──────┐          │
                                           │     │  REST / MCP │          │
                                           │     └──────┬──────┘          │
                                           │        web player            │
                                           └──────────────────────────────┘
```

- **Ingest**: stage-cached CLI (`probe → proxy → shots → asr → frames → embed → index`), idempotent, resumable, one manifest per asset. ASR and proxy encoding use CUDA when present; the CPU path stays correct.
- **Search**: SigLIP frame embeddings fused with dense (`bge-small`) and lexical transcript retrieval, shot-start priors, near-duplicate collapse, moment-level results (±1–3 s) from a LanceDB index.
- **Surfaces**: one query service behind REST and MCP (`search_moments`, `get_moment`, `get_transcript`, `list_assets`), so the web player and agents see one result contract: moment, asset, time range, kind, thumbnail URL, snippet, score, deep link.
- **Eval**: frozen query splits, committed result tables, and a single-stage visual baseline on the same corpus and sampling. The harness is a quality gate, not a CI test.

Design docs: [SPEC.md](SPEC.md) · [high-level design](docs/hld.md) · [tech stack](docs/tech-stack.md) · [ADRs](docs/adr/) · [glossary](CONTEXT.md).

## Reproduce

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), and FFmpeg (`ffprobe` on
`PATH`; libGL for OpenCV). On a clean machine:

```sh
python3 corpus/fetch.py            # download and verify the four films (~2.3 GB)
uv sync
uv run pytest                      # contract tests
uv run ruff check .                # lint

# ingest the corpus one asset at a time, with per-stage timings
for f in corpus/media/*; do [ -f "$f" ] && uv run shotgrep ingest "$f" --work-dir work --verbose; done

# score the frozen queries against your freshly built index
uv run python -m eval --index work/index --queries eval/queries.yaml --corpus corpus/manifest.json --k 10

# or score the committed index directly
uv run python -m eval --index index --queries eval/queries.yaml --corpus corpus/manifest.json --k 10
```

The committed index reproduces the published Recall@5 and MRR exactly; latency
varies with the machine. The eval harness never edits the frozen labels: a new
run appends a dated table to [eval/RESULTS.md](eval/RESULTS.md).

## Corpus and attribution

Ingest, eval, and the demo run on four Blender Foundation open films. Source
media is fetched and verified against a committed manifest and never goes in
git; the demo index (LanceDB tables and thumbnails, ~65 MiB) is committed, and
the playback proxies ride a release asset
([ADR-0004](docs/adr/0004-committed-index-release-media.md)).

The films stay under their original licenses:

- Big Buck Bunny (2008) © Blender Foundation / Peach open movie project. Source: https://peach.blender.org/. License: CC BY 3.0 — https://creativecommons.org/licenses/by/3.0/. No changes; playback uses generated proxies.
- Sintel (2010) © Blender Foundation / Durian open movie project. Source: https://durian.blender.org/. License: CC BY 3.0 — https://creativecommons.org/licenses/by/3.0/. No changes; playback uses generated proxies.
- Tears of Steel (2012) © Blender Foundation / Mango open movie project. Source: https://mango.blender.org/. License: CC BY 3.0 — https://creativecommons.org/licenses/by/3.0/. No changes; playback uses generated proxies.
- Elephants Dream (2006) © Blender Foundation / Orange open movie project. Source: https://orange.blender.org/. License: CC BY 2.5 — https://creativecommons.org/licenses/by/2.5/. No changes; playback uses generated proxies.

Per-asset evidence and the copy-paste block live in
[corpus/ATTRIBUTION.md](corpus/ATTRIBUTION.md). The demo playback proxies are
packed from these films and published as the `demo-media-v4` release asset
([ADR-0004](docs/adr/0004-committed-index-release-media.md)); the recorded
ingest uses the public-domain NASA/JPL clip cited in
[docs/demo/ingest.md](docs/demo/ingest.md).

## Surfaces

The REST endpoints are `GET /search`, `GET /assets`, `GET /moments/{id}`,
`GET /assets/{id}`, and `GET /assets/{id}/transcript`; thumbnails and playback
proxies are served from `/media`. Results carry deep links shaped
`{SHOTGREP_WEB_URL}/watch/{asset_id}?t={seconds}`, defaulting to
`http://localhost:3000` (see
[docs/adr](docs/adr/0002-read-contract-urls-and-deep-links.md)).

`shotgrep mcp` serves the same query service as MCP tools over stdio, which is
what a local coding agent connects to:

```json
{"mcpServers": {"shotgrep": {"command": "uv", "args": ["run", "shotgrep", "mcp", "--work-dir", "work"]}}}
```

`shotgrep serve` mounts the MCP endpoint at `/mcp` alongside REST, so one
process serves both. A deployed host must be named in
`SHOTGREP_MCP_ALLOWED_HOSTS` (comma-separated `host[:port]` allowlist) or the
MCP transport answers `421`; the REST API is unaffected. `NEXT_PUBLIC_API_URL`
points the web app at another API origin; `SHOTGREP_CORS_ORIGINS`
(comma-separated) widens the API's CORS allowlist beyond `SHOTGREP_WEB_URL`.

## Models and configuration

- **ASR:** `large-v3` int8 on CUDA when a device is available, CPU otherwise. Override with `SHOTGREP_ASR_MODEL` and `SHOTGREP_ASR_DEVICE` (`auto`, `cuda`, `cpu`).
- **Visual space:** pinned SigLIP-base ONNX int8 (`Xenova/siglip-base-patch16-224`) for frames and visual queries.
- **Text space:** pinned bge-small-en-v1.5 ONNX int8 (`Xenova/bge-small-en-v1.5`) for transcript segments and transcript queries (see [ADR-0003](docs/adr/0003-two-embedding-spaces.md)).

Both models are fetched once into the Hugging Face cache; the API image bakes
them in at build time. `SHOTGREP_EMBED_MODEL`, `SHOTGREP_EMBED_PRECISION`,
`SHOTGREP_TEXT_EMBED_MODEL`, and `SHOTGREP_TEXT_EMBED_PRECISION` override the
sources; ingest and query must use the same models per space. Ingest writes
per-asset artifacts plus a LanceDB index under `work/index`, so `search` needs
only `--work-dir`. On an NVIDIA machine, install cuBLAS from the NVIDIA wheels
with `uv sync --group cuda`; the transcriber loads them itself, so no
`LD_LIBRARY_PATH` is needed.

## License

[MIT](LICENSE)
