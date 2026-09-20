"""Image and text embeddings from SigLIP, behind one interface.

SiglipOnnxEmbedder hides the runtime: the ONNX int8 export is fetched once
from Hugging Face and cached, images are preprocessed the way the model card
prescribes, and frame and query embeddings go through the same model,
precision, and revision, so both live in one vector space. Swapping model or
precision means editing this module; the stages do not change.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from PIL import Image
from tokenizers import Tokenizer

from pipeline.errors import IngestError

if TYPE_CHECKING:
    from numpy.typing import NDArray

MODEL_ENV = "SHOTGREP_EMBED_MODEL"
PRECISION_ENV = "SHOTGREP_EMBED_PRECISION"
DEFAULT_MODEL = "Xenova/siglip-base-patch16-224"
DEFAULT_PRECISION = "int8"
# The model repo is pinned: vectors built by one revision stay comparable, so
# a revision bump is always a re-embed, never a silent mixed space.
REVISION = "4649052661e53c7000355844105f8a1792088239"
PRECISIONS = {
    "int8": ("onnx/vision_model_int8.onnx", "onnx/text_model_int8.onnx"),
}
IMAGE_SIZE = 224
MAX_TOKENS = 64
BATCH_SIZE = 16
POOLED_OUTPUT = "pooler_output"


class SiglipOnnxEmbedder:
    """SigLIP base: one ONNX session per tower, int8, on the CPU."""

    def __init__(
        self,
        model: str | None = None,
        precision: str | None = None,
        revision: str = REVISION,
    ) -> None:
        self.model = model or os.environ.get(MODEL_ENV) or DEFAULT_MODEL
        self.precision = (precision or os.environ.get(PRECISION_ENV) or DEFAULT_PRECISION).lower()
        if self.precision not in PRECISIONS:
            raise IngestError(f"{PRECISION_ENV} must be one of {', '.join(PRECISIONS)}, got {self.precision!r}")
        self.revision = revision
        self._vision: ort.InferenceSession | None = None
        self._text: ort.InferenceSession | None = None
        self._tokenizer: Tokenizer | None = None

    @property
    def dimension(self) -> int:
        self._load()
        assert self._vision is not None
        pooled = next(output for output in self._vision.get_outputs() if output.name == POOLED_OUTPUT)
        return int(pooled.shape[-1])

    def embed_images(self, paths: Sequence[Path]) -> NDArray[np.float32]:
        """L2-normalized SigLIP vectors, one row per image, in input order."""
        images = [_load_image(path) for path in paths]
        self._load()
        assert self._vision is not None
        batches = []
        for start in range(0, len(images), BATCH_SIZE):
            pixels = np.stack([_pixels(image) for image in images[start : start + BATCH_SIZE]])
            batches.append(self._vision.run([POOLED_OUTPUT], {"pixel_values": pixels.astype(np.float32)})[0])
        if not batches:
            return np.empty((0, self.dimension), dtype=np.float32)
        return _normalize(np.concatenate(batches))

    def embed_text(self, text: str) -> NDArray[np.float32]:
        """The L2-normalized SigLIP vector for one query string."""
        self._load()
        assert self._text is not None and self._tokenizer is not None
        encoded = self._tokenizer.encode_batch([text])
        input_ids = np.array([item.ids for item in encoded], dtype=np.int64)
        pooled = self._text.run([POOLED_OUTPUT], {"input_ids": input_ids})[0]
        return _normalize(pooled)[0]

    def _load(self) -> None:
        if self._vision is not None:
            return
        vision_file, text_file = PRECISIONS[self.precision]
        files = [
            _download(self.model, name, self.revision) for name in (vision_file, text_file, "tokenizer.json")
        ]
        try:
            self._vision = ort.InferenceSession(str(files[0]), providers=["CPUExecutionProvider"])
            self._text = ort.InferenceSession(str(files[1]), providers=["CPUExecutionProvider"])
            tokenizer = Tokenizer.from_file(str(files[2]))
        except Exception as exc:
            raise IngestError(f"could not load SigLIP {self.precision} from {self.model}: {exc}") from exc
        pad_id = tokenizer.token_to_id("</s>")
        if pad_id is None:
            raise IngestError(f"{self.model} tokenizer has no </s> pad token")
        tokenizer.enable_truncation(max_length=MAX_TOKENS)
        tokenizer.enable_padding(length=MAX_TOKENS, pad_id=pad_id, pad_token="</s>")
        self._tokenizer = tokenizer


def _download(model: str, filename: str, revision: str) -> Path:
    try:
        return Path(hf_hub_download(model, filename, revision=revision))
    except Exception as exc:
        raise IngestError(f"could not fetch {filename} from {model}: {exc}") from exc


def _load_image(path: Path) -> Image.Image:
    try:
        with Image.open(path) as image:
            return image.convert("RGB")
    except OSError as exc:
        raise IngestError(f"could not read image {path}: {exc}") from exc


def _pixels(image: Image.Image) -> NDArray[np.float32]:
    square = image.resize((IMAGE_SIZE, IMAGE_SIZE), Image.BICUBIC)
    array = np.asarray(square, dtype=np.float32) / 255.0
    return ((array - 0.5) / 0.5).transpose(2, 0, 1)


def _normalize(vectors: NDArray[np.float32]) -> NDArray[np.float32]:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.maximum(norms, 1e-12)).astype(np.float32)
