# shotgrep

Search video like it's text.

Ask for a moment in plain language — *"the part where he parks the bike at night"* — and get the exact frame back, with jump-to-timestamp links.

**Status:** early build. Ingest pipeline, search API, and web player are under construction.

## Planned surface

- **Ingest** local footage: proxy transcode, shot detection, transcript with word timestamps, visual embeddings
- **Search**: fused transcript + visual retrieval, moment-level results (±1-3s), ANN over a LanceDB index
- **Watch**: browser player that opens results at the right frame
- **Agents**: the index exposed as MCP tools so an agent can search, fetch moments, and read transcripts

## Docs

- [Tech stack](docs/tech-stack.md)
- [High-level design](docs/hld.md)
- [Folder structure](docs/folder-structure.md)
- [Glossary](CONTEXT.md)

## License

[MIT](LICENSE)
