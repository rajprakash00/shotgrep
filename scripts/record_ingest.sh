#!/usr/bin/env bash
# Ingest an arbitrary file end to end and print wall-clock stage timings.
#
#   scripts/record_ingest.sh <file> [work-dir]
#
# Runs from a clean work directory with --verbose, then prints the manifest's
# per-stage table and the realtime factor. The committed recording in
# docs/demo/ingest.cast was produced by running this script under
# `asciinema rec`, so this is the reproducible recipe behind it.
set -euo pipefail

file=${1:?usage: scripts/record_ingest.sh <file> [work-dir]}
work=${2:-work/ingest-demo}

if [ -e "$work" ]; then
  echo "error: $work already exists; remove it for a clean run" >&2
  exit 1
fi

started=$(date +%s)
echo "\$ shotgrep ingest $file --work-dir $work --verbose"
uv run shotgrep ingest "$file" --work-dir "$work" --verbose
elapsed=$(( $(date +%s) - started ))

python3 - "$work" "$file" "$elapsed" <<'PY'
import json
import sys
from pathlib import Path

# Presentation order; mirrors pipeline/stages/__init__.py.
STAGES = ("probe", "proxy", "shots", "asr", "frames", "embed", "index")

work, source, elapsed = Path(sys.argv[1]), Path(sys.argv[2]), int(sys.argv[3])
manifest = json.loads(next(work.glob("*/manifest.json")).read_text(encoding="utf-8"))
asset = manifest["asset"]
duration_s = manifest["stages"]["probe"]["outputs"]["duration_s"]

print()
print(f"file:     {source.name} ({asset['bytes'] / 1e6:.1f} MB, {duration_s:.1f} s)")
print(f"asset id: {asset['id']}")
print(f"status:   {manifest['status']}")
print()
print(f"{'stage':<8} {'wall clock':>11}")
for name in STAGES:
    print(f"{name:<8} {manifest['stages'][name]['duration_ms'] / 1000:>10.1f}s")
print()
print(f"total:    {elapsed} s wall clock, {duration_s / elapsed:.2f}x realtime on this machine")
PY
