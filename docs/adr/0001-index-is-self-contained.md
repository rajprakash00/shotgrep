# ADR-0001: The built index is self-contained

Status: accepted (2026-09-20)

## Context

The demo deploys a prebuilt index (`index/`, committed) without the work
directory (`work/`, disposable and gitignored). Until now, transcript words
lived only in per-asset `transcript.json` artifacts and thumbnails only in
`work/{asset}/thumbnails/`, so a query service pointed at the index alone could
serve neither transcript ranges nor thumbnails.

## Decision

The index stage writes everything the read contract needs into `index/`:

- a `transcripts` table: one row per segment, with text, range, and word
  timestamps;
- the moment thumbnails, mirrored to `index/{asset_id}/thumbnails/`.

`INDEX_VERSION` moves to 2; the query service refuses indexes with rows from
another version and names the missing tables.

## Consequences

- `shotgrep serve --work-dir .` over a checked-out repository serves the demo
  index with no ingest artifacts present.
- The index carries duplicated thumbnails (small JPEGs); work artifacts remain
  the source for reruns.
- A schema change now means a re-index, not only a re-embed.

## Addendum: the index carries the playback proxy

Status: accepted (2026-09-21)

The web player (#9) opens each result's playback proxy at a moment, and the
proxy only existed in `work/{asset_id}/proxy.mp4`, so an index served without
the work directory had nothing to play.

The index stage now mirrors `proxy.mp4` to `index/{asset_id}/proxy.mp4`, next
to the thumbnails, and `INDEX_VERSION` moves to 3. The query service exposes
its public URL as `proxy_url` through asset lookup (`GET /assets/{asset_id}`),
built from `SHOTGREP_API_URL` exactly like `thumbnail_url`.

Playback therefore joins search on the self-contained index, at the cost of a
larger committed index: hosting the demo media is settled in the ship ticket
(#11).
