# Folder structure

```
shotgrep/
├── pipeline/            # Python: ingest stages, model wrappers, CLI
│   ├── stages/          # one module per stage, idempotent, manifest-driven
│   ├── models/          # embedder, transcriber — thin interfaces over pretrained models
│   └── cli.py           # `shotgrep ingest <file> [--from-stage embed] [--workers N]`
├── api/                 # FastAPI: search, moments, transcripts; MCP server
├── web/                 # Next.js: search box, results grid, player with deep links
├── eval/                # queries.yaml, harness, committed result tables
├── index/               # built LanceDB + thumbnails for the demo corpus
├── work/                # per-asset artifacts (gitignored)
├── docs/                # tech-stack.md, hld.md, folder-structure.md, agents/
└── docker-compose.yml
```

## Conventions

- `work/` is disposable. Delete it and re-ingest; nothing else depends on it.
- `index/` is a build output, deliberately committed for the demo corpus so the hosted demo starts instantly.
- `eval/queries.yaml` is frozen once ranking work starts; changes need a dated note.
- Stages never import each other; they communicate through the manifest and files.
- Model wrappers hide the runtime (ONNX/CUDA) behind one interface, so model or precision swaps stay local.
- `docs/agents/` holds tooling configuration, not product docs.
