# shotgrep web

The web player: search box, results grid, and a player that opens each result at its moment.

```sh
pnpm install
pnpm dev        # http://localhost:3000, expects the API on http://localhost:8000
```

Point the app at a different API with `NEXT_PUBLIC_API_URL`. Deep links in API results
are built from the API's `SHOTGREP_WEB_URL`, so run the API with that set to this app's
origin.

```sh
uv run shotgrep serve --work-dir work   # from the repo root
```

```sh
pnpm lint
pnpm typecheck
pnpm test
```

The read contract lives in the repo root: [README](../README.md), [SPEC](../SPEC.md),
and [docs/adr](../docs/adr/).
