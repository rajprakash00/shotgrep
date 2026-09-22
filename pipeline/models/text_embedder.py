"""Text embeddings from bge-small-en-v1.5, behind one interface.

TextOnnxEmbedder hides the runtime: the ONNX int8 export is fetched once from
Hugging Face and cached, transcript segments are embedded bare, and queries
carry the instruction prefix bge expects for retrieval, so both sides live in
one text space distinct from the SigLIP space that holds frames. Swapping model
or precision means editing this module; the stages and the query service do not
change.
"""

from __future__ import annotations

import os
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING

import numpy as np
import onnxruntime as ort
from huggingface_hub import hf_hub_download
from tokenizers import Tokenizer

from pipeline.errors import IngestError

if TYPE_CHECKING:
    from numpy.typing import NDArray

MODEL_ENV = "SHOTGREP_TEXT_EMBED_MODEL"
PRECISION_ENV = "SHOTGREP_TEXT_EMBED_PRECISION"
DEFAULT_MODEL = "Xenova/bge-small-en-v1.5"
DEFAULT_PRECISION = "int8"
# The model repo is pinned: vectors built by one revision stay comparable, so
# a revision bump is always a re-embed, never a silent mixed space.
REVISION = "ea104dacec62c0de699686887e3f920caeb4f3e3"
PRECISIONS = {
    "int8": "onnx/model_quantized.onnx",
}
MAX_TOKENS = 512
BATCH_SIZE = 16
CLS_TOKEN = 0
PAD_TOKEN = "[PAD]"
# bge is trained with this instruction on the query side of retrieval tasks.
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


class TextOnnxEmbedder:
    """bge-small-en-v1.5: one ONNX session, int8, CLS pooling, on the CPU."""

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
        self._session: ort.InferenceSession | None = None
        self._tokenizer: Tokenizer | None = None

    @property
    def dimension(self) -> int:
        self._load()
        assert self._session is not None
        return int(self._session.get_outputs()[0].shape[-1])

    def embed_documents(self, texts: Sequence[str]) -> NDArray[np.float32]:
        """L2-normalized vectors, one row per segment text, in input order."""
        return self._embed(texts)

    def embed_query(self, text: str) -> NDArray[np.float32]:
        """The L2-normalized vector for one query string, instruction included."""
        return self._embed([QUERY_PREFIX + text])[0]

    def _embed(self, texts: Sequence[str]) -> NDArray[np.float32]:
        self._load()
        assert self._session is not None and self._tokenizer is not None
        batches = []
        for start in range(0, len(texts), BATCH_SIZE):
            encoded = self._tokenizer.encode_batch(list(texts[start : start + BATCH_SIZE]))
            hidden = self._session.run(None, self._feeds(encoded))[0]
            batches.append(hidden[:, CLS_TOKEN])
        if not batches:
            return np.empty((0, self.dimension), dtype=np.float32)
        return _normalize(np.concatenate(batches))

    def _feeds(self, encoded) -> dict[str, NDArray[np.int64]]:
        assert self._session is not None
        inputs = {
            "input_ids": np.array([item.ids for item in encoded], dtype=np.int64),
            "attention_mask": np.array([item.attention_mask for item in encoded], dtype=np.int64),
            "token_type_ids": np.array([item.type_ids for item in encoded], dtype=np.int64),
        }
        names = {tensor.name for tensor in self._session.get_inputs()}
        return {name: value for name, value in inputs.items() if name in names}

    def _load(self) -> None:
        if self._session is not None:
            return
        files = [
            _download(self.model, name, self.revision)
            for name in (PRECISIONS[self.precision], "tokenizer.json")
        ]
        try:
            self._session = ort.InferenceSession(str(files[0]), providers=["CPUExecutionProvider"])
            tokenizer = Tokenizer.from_file(str(files[1]))
        except Exception as exc:
            raise IngestError(f"could not load bge {self.precision} from {self.model}: {exc}") from exc
        pad_id = tokenizer.token_to_id(PAD_TOKEN)
        if pad_id is None:
            raise IngestError(f"{self.model} tokenizer has no {PAD_TOKEN} pad token")
        tokenizer.enable_truncation(max_length=MAX_TOKENS)
        tokenizer.enable_padding(pad_id=pad_id, pad_token=PAD_TOKEN)
        self._tokenizer = tokenizer


def _download(model: str, filename: str, revision: str) -> Path:
    try:
        return Path(hf_hub_download(model, filename, revision=revision))
    except Exception as exc:
        raise IngestError(f"could not fetch {filename} from {model}: {exc}") from exc


def _normalize(vectors: NDArray[np.float32]) -> NDArray[np.float32]:
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    return (vectors / np.maximum(norms, 1e-12)).astype(np.float32)
