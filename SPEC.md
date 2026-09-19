# shotgrep v1 — spec

Status: approved. Implementation tickets (GitHub issues) reference this file.
Product docs: [Tech stack](docs/tech-stack.md) · [High-level design](docs/hld.md) · [Folder structure](docs/folder-structure.md) · [Glossary](CONTEXT.md)

## Problem Statement

Video has no grep. A folder of footage is searchable only by filename and by memory, so finding "the part where he parks the bike at night" means scrubbing through hours of timeline. Existing tools either match exact filenames and metadata, or rely on semantic models that feel slow and imprecise, return approximate ranges rather than moments, and are not exposed to agents. There is no small, self-hostable system that turns a folder of video into moment-accurate, fused transcript + visual search with published accuracy and latency numbers.

## Solution

shotgrep ingests a folder of video on one machine and produces a portable index. Search fuses visual embeddings with transcript retrieval, returns moment-level results (±1-3s) with thumbnails and deep links into a web player, and exposes the same index to agents through MCP tools. Quality is measured, not claimed: a fixed corpus with frozen query splits, published Recall@5, MRR, and p50/p95 latency, compared against a single-stage baseline.

## User Stories

1. As a creator, I want to ingest a folder of footage with one command, so that I don't babysit each file.
2. As a creator, I want a per-asset manifest, so that I can see what succeeded and what failed.
3. As a creator, I want to resume ingest from the stage that failed, so that a long transcode is not repeated.
4. As a creator, I want failed assets flagged and skipped, so that one corrupt file does not block the batch.
5. As a creator, I want proxies generated for playback, so that the browser plays smoothly without streaming originals.
6. As a creator, I want shot boundaries detected, so that results can anchor to shot starts.
7. As a creator, I want transcripts with word timestamps, so that speech is searchable and citable.
8. As a creator, I want thumbnails stored, so that results render instantly.
9. As a creator, I want ingest to be idempotent, so that reruns are safe.
10. As a creator with an NVIDIA GPU, I want ASR and proxy encoding to use it, so that ingest is faster; without one, I want the CPU path to stay correct.
11. As a creator, I want to rerun a single stage, so that a model change is cheap.
12. As an editor, I want to search in plain language, so that I can find moments without guessing keywords.
13. As an editor, I want results at moment granularity, so that I can jump close to the right frame.
14. As an editor, I want fused transcript and visual retrieval, so that both quoted speech and visual descriptions work.
15. As an editor, I want near-duplicate results collapsed, so that five adjacent frames do not fill the list.
16. As an editor, I want to filter by asset and time range, so that I can narrow a large library.
17. As an editor, I want every result to carry a deep link, so that I can share a moment.
18. As an editor, I want search to answer in well under a second, so that it feels instant.
19. As a viewer, I want a web player that opens at the moment, so that I can verify a result in one click.
20. As an editor, I want transcript context around a result, so that I understand why it matched.
21. As an agent, I want a search tool, so that I can find moments from a natural-language request.
22. As an agent, I want a moment lookup tool, so that I can inspect metadata and thumbnails for a candidate.
23. As an agent, I want a transcript range tool, so that I can quote precisely.
24. As an agent, I want an asset listing tool, so that I know what the index contains.
25. As an agent, I want deep links in every result, so that I can hand a human a clickable reference.
26. As an agent, I want to save a selection as an edit list, so that an editor can act on my findings.
27. As a maintainer, I want a frozen, labeled query set with difficulty splits, so that ranking changes are measured, not guessed.
28. As a maintainer, I want a naive baseline on the same corpus, so that improvements are attributable to specific decisions.
29. As a maintainer, I want committed result tables, so that quality claims are reproducible.
30. As a reviewer, I want one command that reproduces the benchmark, so that I can verify the numbers myself.
31. As a visitor, I want a hosted demo with a prebuilt corpus, so that I can try search without installing anything.
32. As a reviewer, I want a recorded ingest of an arbitrary file, so that I can see the pipeline works beyond the curated corpus.
33. As a maintainer, I want CI to lint and run the contract tests on a fixture, so that regressions are caught early.
34. As a maintainer, I want the demo to cost a few dollars a month, so that it can stay online.
35. As a maintainer, I want the eval harness to be a quality gate rather than a CI test, so that ranking experiments stay fast.

## Implementation Decisions

- **Ingest is a stage-cached CLI, not a service.** Stages run in order: probe, proxy, shots, asr, frames, embed, index. Each stage reads prior artifacts, writes its own, and updates the asset manifest. Stages are idempotent, resumable from any point, and isolated per asset so one failure never blocks a batch. Concurrency across assets via a worker flag; stages within an asset stay ordered.
- **The manifest is the recovery contract.** Per-stage status, timing, outputs, and errors; partial assets are flagged, never silently indexed.
- **One query service serves both surfaces.** A single search interface backs the REST API and the MCP server, so the web player and agents share one result contract. The web app consumes REST only.
- **Model wrappers hide the runtime.** Embedder and transcriber sit behind one interface each, so model or precision swaps stay local.
- **Embedding policy:** one model and one precision for frame embeddings and query embeddings, so index vectors and query vectors live in the same space. Default is a SigLIP-base ONNX int8 CPU path. GPU is an optional accelerator used for ASR and proxy encoding; CPU-only runs must remain correct and publishable.
- **Sampling policy:** 1 fps plus the first frame of every shot plus transcript anchors; thumbnails persisted as JPEG; raw frames never retained.
- **Retrieval:** ANN over visual moments; keyword/fuzzy retrieval over transcript moments; fusion via score normalization, reciprocal rank fusion, and priors that rank shot starts above mid-shot samples; near-duplicate collapse. Reranking is a pluggable step, off by default until the eval justifies it.
- **Data model:** an assets table and a moments table (moment kinds: shot start, frame, transcript); transcripts stored per asset with word timestamps. The index is versioned and each row records which stages produced it, so a model change is a re-embed, not a full re-ingest.
- **Result contract** (identical from REST and MCP): moment id, asset id, time range, kind, thumbnail URL, snippet, score, deep link.
- **MCP tools:** search moments, get moment, get transcript range, list assets. Stretch: save selection as an edit list (EDL/CSV).
- **Eval harness:** labeled queries with splits (easy, paraphrase, temporal, negation), expected ranges with ±2s tolerance, frozen before tuning begins. Metrics: Recall@5, MRR, p50/p95 latency. Baseline: single-stage visual retrieval on the same corpus and sampling. Results committed as markdown tables.
- **Corpus:** CC-licensed open films with per-asset license verification at ingest; attribution shipped in the README and the demo.
- **Deployment:** API on Fly.io, web on Vercel, prebuilt index committed for the demo corpus so the demo starts instantly. CI on GitHub Actions.
- **Demo shape:** instant search over the prebuilt corpus plus a recorded ingest of an arbitrary file to prove generality. Live upload is deferred.

## Testing Decisions

- Good tests exercise external behavior only: for ingest, that the manifest reaches complete and the asset's moments become queryable; for search, that results carry correct timestamps, kinds, and deep links. Stage internals get no tests.
- Two seams, both confirmed: the ingest CLI contract and the read contract behind REST and MCP. One small fixture clip powers both.
- Deliberately small suite for the build budget: one ingest contract test over the fixture, a handful of read-contract tests, and tool-schema tests. No browser E2E in v1.
- The eval harness is a benchmark gate, not part of CI. CI runs lint plus the contract tests.

## Out of Scope

- Live upload from the website, job queues beyond one machine, multi-tenant isolation.
- Editing, rendering, or export beyond the stretch edit-list tool.
- Model training or fine-tuning.
- Collaboration, version control, auth, and mobile clients.

## Further Notes

- Index and query embeddings must share one precision path; any mixed-precision experiment ships only with an eval table row.
- The read contract must stay identical across REST and MCP so both surfaces present one cognitive model.
- README numbers stay placeholders until the harness has run; no quality claim ships before a measured table exists.
- A recorded arbitrary-file ingest is required for credibility; a capped live upload is an optional stretch.
