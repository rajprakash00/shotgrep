# ADR-0004: The search index is committed; playback media is a release asset

Status: accepted (2026-09-22)

## Context

The demo serves the prebuilt corpus index so it starts instantly, with no
ingest step (#11). The built index is ~404 MiB: ~65 MiB of LanceDB tables and
thumbnails, plus ~339 MiB of playback proxies. ADR-0001's addendum added the
proxies to the self-contained index and left the hosting question to this
ticket.

Committing the whole index would make every clone and CI checkout ~404 MiB, and
the proxies are derived from CC-licensed media that is already fetched by
`corpus/fetch.py`, not source material the repository needs to version.

## Decision

- The search artifacts and thumbnails are committed under `index/`:
  `assets.lance`, `moments.lance`, `transcripts.lance`, and
  `{asset_id}/thumbnails/`. A checkout can answer search with
  `shotgrep serve --work-dir .`.
- The playback proxies are packed into `shotgrep-demo-media-v4.tar` and
  published as a GitHub release asset on the `demo-media-v4` tag.
- `index/media.json` (committed) pins each proxy's path, size, and SHA-256.
  `scripts/demo_media.py` packs, fetches, and verifies the archive; the API
  Dockerfile fetches it at build time, and `SHOTGREP_DEMO_MEDIA_URL` overrides
  the source. `index/*/proxy.mp4` is gitignored so a fetched copy is never
  committed.
- The web player 404s on playback until the media is fetched; search,
  thumbnails, and deep links are unaffected.

## Consequences

- Clones and CI check out ~65 MiB of index, not ~404 MiB.
- Publishing the media is a release step in the deploy runbook
  (`docs/deploy.md`); a new index version means a new release tag and a repack.
- Hash verification makes a stale or corrupted archive a hard error, not a
  broken player.
- If the demo later needs a different media host, only
  `SHOTGREP_DEMO_MEDIA_URL` changes; the manifest and verification stay.
