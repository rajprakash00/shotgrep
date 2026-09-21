"""The read contract: one set of models shared by REST and MCP.

The query service speaks plain dicts; both surfaces validate them into these
models, so a payload change breaks REST and MCP together instead of letting the
two drift. FastAPI uses them as response models, the MCP tools as output
schemas, and `extra="forbid"` keeps the service and the contract in step.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

FORBID_EXTRA = ConfigDict(extra="forbid")
MomentKind = Literal["shot_start", "frame", "transcript"]


class ModelInfo(BaseModel):
    """The embedding model and precision that produced the index."""

    model_config = FORBID_EXTRA

    name: str
    precision: str
    revision: str


class Moment(BaseModel):
    """One retrievable time range inside an asset."""

    model_config = FORBID_EXTRA

    moment_id: str = Field(description="Stable id of the moment in the index.")
    asset_id: str = Field(description="Content hash of the asset holding the moment.")
    kind: MomentKind = Field(description="One of shot_start, frame, or transcript.")
    start_s: float = Field(description="Moment start in seconds from the asset start.")
    end_s: float = Field(description="Moment end in seconds.")
    thumbnail_url: str = Field(description="Public URL of the moment's JPEG thumbnail.")
    snippet: str | None = Field(description="Transcript text for transcript moments; null otherwise.")
    score: float | None = Field(description="Fused relevance score; null for a direct lookup.")
    deep_link: str = Field(description="Web player URL that opens at the moment.")


class SearchResponse(BaseModel):
    """Ranked moments for one query, fused across visual and transcript retrieval."""

    model_config = FORBID_EXTRA

    query: str
    model: ModelInfo
    results: list[Moment]


class Asset(BaseModel):
    """One media file in the index."""

    model_config = FORBID_EXTRA

    asset_id: str = Field(description="Content hash of the asset.")
    filename: str
    duration_s: float
    fps: float
    codec: str
    status: str
    proxy_url: str = Field(description="Public URL of the asset's playback proxy.")


class AssetList(BaseModel):
    """Every asset in the index, ordered by filename."""

    model_config = FORBID_EXTRA

    assets: list[Asset]


class TranscriptWord(BaseModel):
    """One word with its absolute timestamps."""

    model_config = FORBID_EXTRA

    word: str
    start_s: float
    end_s: float


class TranscriptSegment(BaseModel):
    """One transcript segment with word timestamps."""

    model_config = FORBID_EXTRA

    text: str
    start_s: float
    end_s: float
    words: list[TranscriptWord]


class Transcript(BaseModel):
    """The transcript segments overlapping a time range of one asset."""

    model_config = FORBID_EXTRA

    asset_id: str
    start_s: float
    end_s: float
    segments: list[TranscriptSegment]
