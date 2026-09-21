# shotgrep eval results

Frozen query set: `eval/queries.yaml` (sha256 `5fca0c6edd1e45c51d2f9d60c64b880f38d67aed0ba2bbb5446f6e75b1c51c22`). Corpus manifest: `corpus/manifest.json` (sha256 `8abede3de0f641b077adf1ebfe42dd5cac65204896834e3322644969ae9072ef`). Index: Xenova/siglip-base-patch16-224 int8 rev 4649052661e53c7000355844105f8a1792088239; 4 assets, 3797 moments, index version 2.
Reproduce with `uv run python -m eval --index work/index --queries eval/queries.yaml --corpus corpus/manifest.json`.

> **Freeze note.** The labels and tolerance in `eval/queries.yaml` are frozen; the query-set and corpus hashes above pin those inputs, and the index line identifies the embedding model, revision, and size. A later ranking or pipeline change must not edit the labels — it appends a new dated table below.

## 2026-09-21

| System | Split | N | Recall@5 | MRR | p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|---|
| shipped fused | overall | 64 | 0.609 | 0.459 | 114 | 144 |
| shipped fused | easy | 16 | 0.562 | 0.484 | 121 | 131 |
| shipped fused | paraphrase | 16 | 0.562 | 0.393 | 110 | 147 |
| shipped fused | temporal | 16 | 0.625 | 0.361 | 134 | 156 |
| shipped fused | negation | 16 | 0.688 | 0.599 | 110 | 134 |
| baseline visual | overall | 64 | 0.578 | 0.420 | 48 | 61 |
| baseline visual | easy | 16 | 0.500 | 0.458 | 48 | 58 |
| baseline visual | paraphrase | 16 | 0.562 | 0.285 | 48 | 57 |
| baseline visual | temporal | 16 | 0.562 | 0.375 | 48 | 62 |
| baseline visual | negation | 16 | 0.688 | 0.562 | 47 | 65 |
