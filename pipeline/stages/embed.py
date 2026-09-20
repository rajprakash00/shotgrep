"""Embed stage: one SigLIP vector per frame sample.

Reads frames.json, embeds every stored thumbnail with the shared embedder, and
writes embeddings.npy whose rows line up with the frame samples. Model,
precision, and revision land in the manifest so a model change is a re-embed.
See pipeline/stages/__init__.py for the stage protocol.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from pipeline.errors import IngestError
from pipeline.jsonio import read_json
from pipeline.models.embedder import SiglipOnnxEmbedder

NAME = "embed"
ARTIFACT = "embeddings.npy"
FRAMES_ARTIFACT = "frames.json"


def run(source: Path, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    frames = _artifact(out_dir)
    samples = frames["samples"]
    embedder = SiglipOnnxEmbedder()
    embeddings = embedder.embed_images([out_dir / sample["thumbnail"] for sample in samples])
    _save(out_dir / ARTIFACT, embeddings)
    return {
        "artifact": ARTIFACT,
        "count": len(samples),
        "dimension": embedder.dimension,
        "model": embedder.model,
        "precision": embedder.precision,
        "revision": embedder.revision,
    }


def _artifact(out_dir: Path) -> dict:
    path = out_dir / FRAMES_ARTIFACT
    if not path.is_file():
        raise IngestError(f"{FRAMES_ARTIFACT} is missing; run the frames stage first")
    return read_json(path)


def _save(path: Path, embeddings: np.ndarray) -> None:
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as handle:
        np.save(handle, embeddings)
    os.replace(temp, path)
