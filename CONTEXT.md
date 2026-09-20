# shotgrep context

Shared vocabulary for this project. Use these terms in code, docs, and issues.

| Term | Meaning |
|---|---|
| **asset** | One media file tracked by the system. Identified by content hash. |
| **ingest** | The offline batch pipeline that turns an asset into searchable artifacts. |
| **stage** | One idempotent step of ingest. Reads artifacts, writes artifacts, updates the manifest. Resumable. |
| **manifest** | Per-asset JSON recording each stage's status and outputs. The unit of recovery. |
| **proxy** | Low-bitrate transcode used for playback only. Never used for analysis. |
| **shot** | A contiguous camera take, detected from frame deltas. |
| **moment** | A retrievable time range inside an asset. Kinds: `shot_start`, `frame`, `transcript`. |
| **frame sample** | A stored JPEG + embedding at a sampled time. Samples: 1 fps, each shot start, transcript anchors. |
| **embedding** | A vector from SigLIP-base. One model and one precision for frames and queries. |
| **index** | The LanceDB store of assets, moments, and transcripts, plus thumbnails. Versioned per corpus, self-contained. |
| **query service** | The one read interface behind REST and MCP: retrieval, fusion, dedupe, lookups. |
| **corpus** | A fixed set of assets used for the demo and the eval. |
| **query split** | Eval grouping: `easy`, `paraphrase`, `temporal`, `negation`. Frozen before tuning. |
| **deep link** | A URL that opens the web player at a moment's timestamp. |
| **tool** | An MCP function an agent can call over the index. |
