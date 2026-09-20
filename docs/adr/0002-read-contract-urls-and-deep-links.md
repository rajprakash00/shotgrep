# ADR-0002: The read contract carries public URLs and deep links

Status: accepted (2026-09-20)

## Context

The spec requires one result contract from REST and MCP, with a thumbnail URL
and a deep link in every result. The web player (#9) must open a moment from a
link that survives reload, and the API (#11) is served from a different origin
than the web app.

## Decision

Every result carries:

- `thumbnail_url`: `{SHOTGREP_API_URL}/media/{asset_id}/thumbnails/{ms}.jpg`,
  served by the API's static mount of the index directory;
- `deep_link`: `{SHOTGREP_WEB_URL}/watch/{asset_id}?t={seconds}`, where seconds
  is the moment start with trailing zeros trimmed (`?t=2`, `?t=4.44`).

Defaults are `http://localhost:8000` (API) and `http://localhost:3000` (web).
A service builds both from its own configuration, so REST, MCP, and the CLI
return byte-identical URLs for the same index.

## Consequences

- The web player implements `/watch/{asset_id}` reading `t` in seconds.
- Deployments set `SHOTGREP_API_URL` and `SHOTGREP_WEB_URL`; no URL is baked
  into the index.
- Changing either URL shape is a contract change for REST and MCP together.
