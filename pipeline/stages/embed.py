"""Embed stage: one SigLIP vector per frame sample, one bge vector per segment.

Reads frames.json and transcript.json, embeds every stored thumbnail with the
visual embedder and every transcript segment with the text embedder, and writes
embeddings.npy and text_embeddings.npy whose rows line up with the samples and
segments. Model, precision, and revision land in the manifest for each space,
so a model change is a re-embed. See pipeline/stages/__init__.py for the stage
protocol.
"""

from __future__ import annotations

import os
from pathlib import Path

import numpy as np

from pipeline.errors import IngestError
from pipeline.jsonio import read_json
from pipeline.models.embedder import SiglipOnnxEmbedder
from pipeline.models.text_embedder import TextOnnxEmbedder

NAME = "embed"
ARTIFACT = "embeddings.npy"
TEXT_ARTIFACT = "text_embeddings.npy"
FRAMES_ARTIFACT = "frames.json"
TRANSCRIPT_ARTIFACT = "transcript.json"


def run(source: Path, out_dir: Path) -> dict:
    out_dir = Path(out_dir)
    frames = _artifact(out_dir, FRAMES_ARTIFACT)
    samples = frames["samples"]
    embedder = SiglipOnnxEmbedder()
    embeddings = embedder.embed_images([out_dir / sample["thumbnail"] for sample in samples])
    _save(out_dir / ARTIFACT, embeddings)

    segments = _artifact(out_dir, TRANSCRIPT_ARTIFACT)["segments"]
    text_embedder = TextOnnxEmbedder()
    text_embeddings = text_embedder.embed_documents([segment["text"] for segment in segments])
    _save(out_dir / TEXT_ARTIFACT, text_embeddings)

    return {
        "artifact": ARTIFACT,
        "count": len(samples),
        "dimension": embedder.dimension,
        "model": embedder.model,
        "precision": embedder.precision,
        "revision": embedder.revision,
        "text_artifact": TEXT_ARTIFACT,
        "text_count": len(segments),
        "text_dimension": text_embedder.dimension,
        "text_model": text_embedder.model,
        "text_precision": text_embedder.precision,
        "text_revision": text_embedder.revision,
    }


def _artifact(out_dir: Path, name: str) -> dict:
    path = out_dir / name
    if not path.is_file():
        raise IngestError(f"{name} is missing; run the earlier stages first")
    return read_json(path)


def _save(path: Path, embeddings: np.ndarray) -> None:
    temp = path.with_name(path.name + ".tmp")
    with temp.open("wb") as handle:
        np.save(handle, embeddings)
    os.replace(temp, path)
