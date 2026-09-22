# High-level design

## Goal

Turn a folder of video into a searchable index of moments, and expose it to both a web player and an agent.

## Two planes

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

## Ingest plane

Stage order: `probe → proxy → shots → asr → frames → embed → index`.

- Every stage is a pure function of the work directory: reads prior artifacts, writes its own, updates the manifest.
- Idempotent: rerunning a completed stage is a no-op unless `--force`.
- Resumable: `--from-stage` starts at any stage; one failed asset never blocks the run.
- Parallel: `--workers N` processes independent assets concurrently; stages within an asset stay ordered.
- The manifest is the recovery contract: status, timing, outputs, and errors per stage.

## Online plane

- Query text is embedded in the same space as the index channel it queries: SigLIP for visual moments, the text embedder for transcript moments (ADR-0003).
- Candidate retrieval: ANN over visual moments, ANN over transcript segment vectors, plus keyword/fuzzy retrieval over transcript moments, all in the same query service, then fused.
- Fusion: score normalization + reciprocal rank fusion + priors (shot starts rank above mid-shot samples), then a greedy MMR-style collapse so results are not five adjacent frames.
- Results carry: moment id, asset, time range, thumbnail, snippet, score, deep link.
- Rerank is a pluggable step, off until the eval justifies it.

## Data model

- `assets`: id (content hash), path, duration, fps, codec, status.
- `moments`: id, asset_id, t_start, t_end, kind, thumbnail path, embedding, snippet, shot_id. Transcript moments also carry the text embedder's vector and its model metadata; other kinds leave it null.
- `transcripts`: per-asset word list, one row per segment; the source of range reads. Moment text vectors are stored on the transcript moments that anchor these segments.
- The built index also carries the moment thumbnails, so it serves on its own
  (ADR-0001).

## Agent surface (MCP)

- `search_moments(query, k?, asset?, start_s?, end_s?)`
- `get_moment(moment_id)`
- `get_transcript(asset_id, start_s?, end_s?)`
- `list_assets()`
- Stretch: `save_selection(ids, label)` → EDL/CSV.

Tools return compact structured results with absolute timestamps and deep links.
No answer tool — the agent composes.

## Failure model

- Per-stage retries with backoff for transient errors. Deterministic failures mark the stage failed and move on.
- Partial assets are flagged, never silently indexed.
- The index records which stages produced each row, so a model change is a re-embed, not a full re-ingest.

## Quality gate

The eval harness is the arbiter of ranking changes: fixed corpus, frozen query splits, published numbers. No ranking change ships without a before/after table.

## Out of scope (v1)

Live upload, queues, multi-tenancy, editing/rendering, collaboration, model training. The design notes where each would attach.
