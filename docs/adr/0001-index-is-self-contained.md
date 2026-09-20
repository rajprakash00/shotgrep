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
