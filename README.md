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

- [Spec](SPEC.md)
- [Tech stack](docs/tech-stack.md)
- [High-level design](docs/hld.md)
- [Folder structure](docs/folder-structure.md)
- [Corpus](corpus/README.md)
- [Glossary](CONTEXT.md)

## Corpus and attribution

Ingest, eval, and the demo run on four Blender Foundation open films. Media is
fetched and verified against a committed manifest; no binaries go in git.

```sh
python3 corpus/fetch.py
```

The films stay under their original licenses:

- Big Buck Bunny (2008) © Blender Foundation / Peach open movie project. Source: https://peach.blender.org/. License: CC BY 3.0 — https://creativecommons.org/licenses/by/3.0/. No changes; playback uses generated proxies.
- Sintel (2010) © Blender Foundation / Durian open movie project. Source: https://durian.blender.org/. License: CC BY 3.0 — https://creativecommons.org/licenses/by/3.0/. No changes; playback uses generated proxies.
- Tears of Steel (2012) © Blender Foundation / Mango open movie project. Source: https://mango.blender.org/. License: CC BY 3.0 — https://creativecommons.org/licenses/by/3.0/. No changes; playback uses generated proxies.
- Elephants Dream (2006) © Blender Foundation / Orange open movie project. Source: https://orange.blender.org/. License: CC BY 2.5 — https://creativecommons.org/licenses/by/2.5/. No changes; playback uses generated proxies.

Per-asset evidence and the copy-paste block live in
[corpus/ATTRIBUTION.md](corpus/ATTRIBUTION.md).

## Development

Ingest needs Python 3.12+, [uv](https://docs.astral.sh/uv/), and FFmpeg
(`ffprobe` on `PATH`).

```sh
uv sync
uv run pytest        # contract tests
uv run ruff check .  # lint
uv run shotgrep ingest <file> --work-dir work
```

## License

[MIT](LICENSE)
