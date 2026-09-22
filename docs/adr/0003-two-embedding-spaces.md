# ADR-0003: Two embedding spaces — SigLIP for frames, bge for transcripts

Status: accepted (2026-09-22)

## Context

The v1 read path had two retrieval channels: visual ANN over SigLIP frame
embeddings, and lexical keyword/fuzzy retrieval over transcript moments. The
2026-09-21 eval showed the lexical channel returning a hit for 1 of 64 frozen
queries, because most spoken lines are paraphrased rather than quoted and the
`MIN_COVERAGE` gate (`api/retrieval.py`) drops partial matches. The 2026-09-22
rerun confirmed it: dialogue-heavy Tears of Steel was the weakest film (6/16
correct at k=5), and the analysis (`eval/ANALYSIS.md`) named the transcript
channel the largest expected gain.

## Decision

Add a dense transcript channel with a dedicated small text embedder:

- `bge-small-en-v1.5` (MIT, 33.4M params, 384d) exported to ONNX int8, hidden
  behind `pipeline/models/text_embedder.py` much as SigLIP is hidden behind
  `pipeline/models/embedder.py`. Queries carry bge's retrieval instruction
  prefix; segments are embedded bare. Segment-level vectors first; window
  embeddings only if dialogue recall is still short after segment-level.
- The index (version 4) stores a `text_embedding` vector on transcript moments
  plus `text_embedding_model`, `text_embedding_precision`, and
  `text_embedding_revision`, so each space is versioned and validated on its
  own. The visual columns keep their own metadata in the same row.
- The query service fuses three channels: visual ANN, dense transcript, and the
  untouched lexical transcript channel. The dense channel carries a confidence
  floor (`MIN_SIMILARITY = 0.6`): bge similarities live in about [0.6, 1], and
  without the floor every segment looks alike to every query and the channel
  floods fusion with noise. The floor is measured in the rerun addendum below;
  one ranking change ships per result table.
- The read contract does not change: the same `search` result shape carries the
  new channel's hits through REST and MCP.

This deviates from `SPEC.md:58` ("one model and one precision for frame
embeddings and query embeddings"): there are now two embedding spaces, each
internally consistent. Frames and visual queries still share one model and
precision; transcript segments and transcript queries share another.

## Rejected alternatives

- **SigLIP's text tower for transcripts.** Text–text similarity is
  off-distribution for a model trained on image–text pairs; reusing the runtime
  would not make transcript search stronger.
- **Lexical-only transcript retrieval (keep the status quo).** The 2026-09-22
  baseline is the measurement of that option: lexical retrieval found 1 of 64
  queries, and no threshold change makes a keyword matcher semantic.
- **Loosening the lexical gate instead of adding a vector channel.** The
  analysis showed paraphrases fail by a wide margin; lowering `MIN_COVERAGE`
  admits noise rather than recall, and a fuzzy gate is not a semantic model.
- **Replacing the lexical channel.** Words still matter for exact quotes and
  names; the channels are complementary and fuse by rank.

## Consequences

- Ingest embeds every transcript segment; the `embed` stage writes
  `text_embeddings.npy` beside `embeddings.npy`. `INDEX_VERSION` moves to 4, so
  an older index is refused and a re-embed is a re-index.
- Query latency grows by one model load and one small ONNX forward pass; the
  committed results table records the p50/p95 at k=10.
- A model or precision swap in either space stays local to its wrapper and is
  caught by the per-channel embedding-space check in `api/service.py`.

## Addendum: rerun outcome (2026-09-22)

The dense transcript channel shipped with a confidence gate
(`MIN_SIMILARITY = 0.6`): below bge's similarity interval every segment looks
alike, and the first, ungated run flooded visual queries with weak matches —
its overall Recall@5 was 0.562, below the 0.609 baseline. The gated run scored
0.688 on the frozen 64-query set, same corpus, index version 4, k=10:

| Film | 2026-09-22 baseline | dense (gated) |
|---|---|---|
| Big Buck Bunny | 0.812 | 0.812 |
| Elephants Dream | 0.562 | 0.562 |
| Sintel | 0.688 | 0.875 |
| Tears of Steel | 0.375 | 0.500 |

Overall Recall@5 moved 0.609 → 0.688 and MRR 0.459 → 0.495; p50 latency grew
125 ms → 189 ms. Sintel and Tears of Steel improve; Elephants Dream holds
rather than improves, because its paraphrases sit below the gate (the ungated
variant scored it 0.375, worse than not using the channel). The full tables are
appended to `eval/RESULTS.md`, including the rejected ungated measurement, and
the lexical channel and its gate are untouched: the delta is the dense channel
joined to the same fusion, with the reweighting any additional channel brings.
