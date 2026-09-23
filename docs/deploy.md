# Deploying the demo

The demo has three pieces: the API on Fly.io, the web player on Vercel, and
the playback media as a GitHub release asset. The committed `index/` carries
the search tables, transcripts, and thumbnails; the API image fetches the
proxies at build time, so the demo answers instantly with no ingest step.

Cost target: Fly `shared-cpu-1x` with 1 GB always on is roughly $5–6/month;
Vercel Hobby and GitHub releases are free. Playback streams 32–138 MiB per
film, so heavy use adds Fly egress.

## Prerequisites

- `flyctl` authenticated (`fly auth login`)
- `vercel` CLI authenticated (`pnpm dlx vercel login`) or the Vercel dashboard
- `gh` authenticated against this repository
- The media archive built: `python3 scripts/demo_media.py pack` (writes
  `dist/shotgrep-demo-media-v4.tar` and `index/media.json`)

## 1. Publish the playback media

The archive is ~339 MiB; git holds the search index, not the video. Publish it
once, from a checkout of `main` after the ship commit lands:

```sh
gh release create demo-media-v4 \
  --title "Demo playback media v4" \
  --notes "Playback proxies for the committed index (index version 4). Verify with python3 scripts/demo_media.py verify." \
  dist/shotgrep-demo-media-v4.tar
```

`scripts/demo_media.py fetch` discovers the asset by name from this tag, so no
URL is hardcoded in the image. The image build treats a missing release as a
warning (search still works) but a corrupt archive as a hard failure. To use a
different host, set `SHOTGREP_DEMO_MEDIA_URL` (env or Docker build arg) to the
archive URL.

## 2. Deploy the API on Fly.io

Edit `fly.toml`: set `app` to an available name, and set `SHOTGREP_API_URL`,
`SHOTGREP_WEB_URL`, and `SHOTGREP_MCP_ALLOWED_HOSTS` to the hosts you will use
(the web URL can be corrected after step 3). Then:

```sh
fly launch --no-deploy --copy-config
fly deploy
curl -sS https://<app>.fly.dev/health
```

`fly deploy` builds the root `Dockerfile`, fetches the release asset, bakes the
pinned ONNX models into the image, and starts one always-on machine. The image
also serves the MCP endpoint at `/mcp`; `SHOTGREP_MCP_ALLOWED_HOSTS` must name
the Fly host or the transport answers `421` (REST is unaffected).

## 3. Deploy the web player on Vercel

The app inlines `NEXT_PUBLIC_API_URL` at build time, so set it to the API
origin before deploying:

```sh
cd web
pnpm dlx vercel link
pnpm dlx vercel env add NEXT_PUBLIC_API_URL production
# paste https://<app>.fly.dev when prompted
pnpm dlx vercel deploy --prod
```

Then point the API's CORS and deep links at the web origin and restart:

```sh
fly secrets set SHOTGREP_WEB_URL=https://<web>.vercel.app
```

## 4. Verify

```sh
curl -sS "https://<app>.fly.dev/assets" | python3 -m json.tool | head
curl -sS "https://<app>.fly.dev/search?q=a%20bridge&k=3" | python3 -m json.tool | head -40
```

The search response must carry `thumbnail_url` and `deep_link` values that
resolve against the deployed hosts; opening a deep link must play the proxy at
the moment's timestamp. The MCP endpoint is reachable with the same allowlist:

```sh
curl -sS https://<app>.fly.dev/mcp \
  -H 'content-type: application/json' \
  -H 'accept: application/json, text/event-stream' \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"curl","version":"0"}}}'
```

## Updating the demo index

Re-ingest the corpus, then repack and redeploy:

```sh
python3 scripts/demo_media.py pack          # refresh index/media.json and the archive
python3 scripts/demo_media.py verify
gh release create demo-media-v5 dist/shotgrep-demo-media-v5.tar   # bump on index-version changes
fly deploy --no-cache                        # pick up the new index and media
```

If the index version changes, update `INDEX_VERSION` in `scripts/demo_media.py`
and the release tag in this document to match `pipeline/stages/index.py`.

## Local demo

```sh
docker compose up --build   # API on :8000, web on :3000
```

The API container fetches the release asset during build; without it, search
and thumbnails still work and playback 404s. Build the archive locally with
`python3 scripts/demo_media.py pack` and pass it with
`--build-arg SHOTGREP_DEMO_MEDIA_URL=<url>` if you want playback before the
release exists.
