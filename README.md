# shotgrep

Search video like it's text.

Ask for a moment in plain language — *"the part where he parks the bike at night"* — and get the exact frame back, with jump-to-timestamp links.

**Status:** early build. Ingest produces a searchable index; the CLI and REST
API answer fused visual + transcript queries and serve moment thumbnails and
transcripts; the web player and eval harness are under construction.

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
uv run shotgrep search "the part where he parks the bike at night" --work-dir work
uv run shotgrep serve --work-dir work   # REST on http://localhost:8000
```

The REST endpoints are `GET /search`, `GET /moments/{id}`, and
`GET /assets/{id}/transcript`; thumbnails are served from `/media`. Results
carry deep links shaped `{SHOTGREP_WEB_URL}/watch/{asset_id}?t={seconds}`,
defaulting to `http://localhost:3000` (see
[docs/adr](docs/adr/0002-read-contract-urls-and-deep-links.md)).

ASR defaults to `large-v3` int8 on CUDA when a device is available, CPU
otherwise. Override with `SHOTGREP_ASR_MODEL` and `SHOTGREP_ASR_DEVICE`
(`auto`, `cuda`, `cpu`); the contract tests pin a tiny model on CPU.

Frame and query embeddings come from pinned SigLIP-base ONNX int8 assets
(`Xenova/siglip-base-patch16-224`), fetched once into the Hugging Face cache.
`SHOTGREP_EMBED_MODEL` and `SHOTGREP_EMBED_PRECISION` (default `int8`) override
the source; ingest and query must use the same pair. Ingest writes per-asset
artifacts plus a LanceDB index under `work/index`, so `search` needs only
`--work-dir`.

On an NVIDIA machine, install cuBLAS from the NVIDIA wheels:

```sh
uv sync --group cuda
```

The transcriber loads them itself, so no `LD_LIBRARY_PATH` is needed. A plain
`uv sync` removes the group; add `--group cuda` to restore it.

## License

[MIT](LICENSE)
