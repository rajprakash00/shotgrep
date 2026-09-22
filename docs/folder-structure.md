# Folder structure

```
shotgrep/
├── pipeline/            # Python: ingest stages, manifest, model wrappers, CLI
│   ├── stages/          # one module per stage, idempotent, manifest-driven
│   ├── models/          # embedder, transcriber — thin interfaces over pretrained models
│   └── cli.py           # `shotgrep ingest <file> [--from-stage STAGE] [--verbose]`
├── api/                 # FastAPI: search, moments, transcripts; MCP server
├── web/                 # Next.js: search box, results grid, player with deep links
├── tests/               # contract tests for the public seams, plus fixtures/
├── corpus/              # manifest, fetch/verify tool, attribution (media gitignored)
├── eval/                # queries.yaml, harness, committed result tables
├── index/               # committed demo index: LanceDB tables + thumbnails
├── scripts/             # demo media pack/fetch/verify, recorded-ingest recipe
├── work/                # per-asset artifacts (gitignored)
├── docs/                # tech-stack.md, hld.md, deploy.md, demo/, agents/
├── Dockerfile           # demo API image (REST + MCP + media)
├── fly.toml             # Fly.io config for the demo API
└── docker-compose.yml   # local demo: API + web
```

## Conventions

- `work/` is disposable. Delete it and re-ingest; nothing else depends on it.
- `corpus/media/` is fetched by `corpus/fetch.py`, verified against the committed `corpus/manifest.json`, and never committed. Ingest reads source media from there.
- `index/` commits the demo corpus search tables and thumbnails, not the playback proxies: those ship as a release asset fetched by `scripts/demo_media.py` (ADR-0004).
- `scripts/` holds standard-library dev tools: `demo_media.py` packs, fetches, and verifies the playback media; `record_ingest.sh` is the recorded-ingest recipe.
- `eval/queries.yaml` is frozen once ranking work starts; changes need a dated note.
- Stages never import each other; they communicate through the manifest and files.
- Contract tests live in `tests/` and drive public seams only (the CLI, the read
  contract); stage internals get no tests.
- Model wrappers hide the runtime (ONNX/CUDA) behind one interface, so model or precision swaps stay local.
- `docs/agents/` holds tooling configuration, not product docs.
