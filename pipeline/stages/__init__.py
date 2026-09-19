"""Ingest stages, in pipeline order.

Each stage module exposes NAME and run(source, out_dir) -> dict outputs.
Stages never import each other; they communicate through the manifest and
files. Adding a stage means adding it here in order.
"""

from __future__ import annotations

from pipeline.stages import probe

STAGES = (probe,)
