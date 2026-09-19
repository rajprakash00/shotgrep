# Corpus

A fixed, reproducible set of CC-licensed open films used by ingest, the eval
harness, and the demo. Media is fetched from the Blender Foundation's download
server, verified against a committed manifest, and never committed to git.

## Films

| id | Film | Year | Duration | Media size | License |
|---|---|---|---|---|---|
| `big-buck-bunny` | Big Buck Bunny | 2008 | 9:56 | 115.7 MiB | CC BY 3.0 |
| `sintel` | Sintel | 2010 | 14:48 | 649.7 MiB | CC BY 3.0 |
| `tears-of-steel` | Tears of Steel | 2012 | 12:14 | 354.9 MiB | CC BY 3.0 |
| `elephants-dream` | Elephants Dream | 2006 | 10:58 | 98.8 MiB | CC BY 2.5 |

Sources, exact durations, sizes, and SHA-256 hashes live in
[`manifest.json`](manifest.json). Attribution text is in
[`ATTRIBUTION.md`](ATTRIBUTION.md).

## Fetch

```
python3 corpus/fetch.py                  # download missing or invalid media, verify it
python3 corpus/fetch.py --check          # verify existing files, no network
python3 corpus/fetch.py --verify-licenses # re-check license evidence pages
python3 corpus/fetch.py --only sintel    # limit to one asset (repeatable)
python3 corpus/fetch.py --update         # re-download and re-pin the manifest
```

The first run downloads about 1.2 GiB into `corpus/media/` (gitignored).
Downloads resume from a `.part` file, and zip archives are verified by hash
before extraction. `--keep-archives` keeps the downloaded zips.

`--check` is the reproducibility contract: it recomputes SHA-256, size, and
container duration for every film and fails if anything drifted. Archive
hashes in the manifest are verified whenever an archive is downloaded; after
extraction the archive is deleted, so `--check` re-verifies media files only.
`fetch.py` uses only the Python standard library; a clean machine needs
Python 3.12+.

## Manifest

This corpus manifest is an inventory of source films, distinct from the
per-asset ingest manifest described in `CONTEXT.md`. Each asset records:

| Field | Meaning |
|---|---|
| `id` | Stable slug used by scripts and docs |
| `title`, `year`, `author` | Credit data |
| `license`, `license_url` | SPDX-style id and license deed |
| `license_evidence_url`, `license_evidence_quote` | Official page and the quoted statement `--verify-licenses` checks |
| `source_page`, `source_url` | Film's project page and the exact download URL |
| `archive_member` | Member to extract when the source is a zip |
| `filename`, `container` | Local file name and container kind |
| `duration_s`, `bytes`, `sha256` | Pinned media facts |
| `archive_bytes`, `archive_sha256` | Pinned source archive facts (zips only) |
| `attribution` | Ready-to-ship CC BY credit line |

`--update` rewrites the derived fields after a download. Treat the committed
manifest as frozen: any change to a pinned hash should be an explicit,
reviewable commit.

## Tests

```
python3 -m unittest discover -s corpus -p 'test_*.py'
```

The suite covers the manifest contract, attribution completeness, the MP4/MOV
and Matroska duration parsers, download/verification behavior, and license
quote matching. It needs no network.

## Adding a film

1. Add an entry to `manifest.json` with source, license, evidence quote, and
   attribution (leave derived fields `null`).
2. Verify the license statement appears on the evidence page.
3. Run `python3 corpus/fetch.py --update --only <id>`.
4. Add the attribution line to `ATTRIBUTION.md` and the README.
