"""The MCP surface: the same QueryService behind typed tools.

`create_mcp` registers four read tools — search moments, get moment, get
transcript range, list assets — whose handlers do nothing but call
QueryService and validate its payload into the shared contract models
(api/contracts.py). There is no second query path: REST, MCP, and the CLI all
read the index through this one service, so tool results are byte-identical to
the REST response for the same query. See `shotgrep mcp` in pipeline/cli.py.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from mcp.server import MCPServer
from mcp.server.mcpserver.exceptions import ToolError
from pydantic import Field

from api.contracts import AssetList, Moment, SearchResponse, Transcript
from api.service import DEFAULT_K, MAX_K, NotFoundError, QueryService
from pipeline.errors import IngestError

INSTRUCTIONS = (
    "Search a local video index of moments. Use search_moments to find "
    "candidates in plain language, get_moment to inspect one candidate, "
    "get_transcript to quote speech with word timestamps, and list_assets to "
    "see what the index holds. Every moment carries absolute timestamps and a "
    "deep link into the web player."
)


def create_mcp(service: QueryService, *, name: str = "shotgrep") -> MCPServer:
    """Build the MCP server over one query service; handlers only delegate."""
    mcp = MCPServer(name, instructions=INSTRUCTIONS)

    @mcp.tool()
    def search_moments(
        query: Annotated[str, Field(description="Plain-language description of the moment.")],
        k: Annotated[
            int,
            Field(ge=1, le=MAX_K, description="Maximum number of moments to return."),
        ] = DEFAULT_K,
        asset: Annotated[
            str | None,
            Field(description="Only return moments of this asset id."),
        ] = None,
        start_s: Annotated[
            float | None,
            Field(description="Only return moments overlapping this start time in seconds."),
        ] = None,
        end_s: Annotated[
            float | None,
            Field(description="Only return moments overlapping this end time in seconds."),
        ] = None,
    ) -> SearchResponse:
        """Find moments matching a query, fusing visual and transcript retrieval.

        Results are ranked with timestamps, thumbnails, snippets, and deep
        links, so a candidate can be cited without a second lookup.
        """
        payload = _call_service(
            service.search,
            query,
            k=k,
            asset=asset,
            start_s=start_s,
            end_s=end_s,
        )
        return SearchResponse.model_validate(payload)

    @mcp.tool()
    def get_moment(
        moment_id: Annotated[str, Field(description="Moment id from a search result.")],
    ) -> Moment:
        """Fetch one indexed moment by id, with its thumbnail and deep link.

        Scores are null: this is a direct lookup, not a ranked result.
        """
        return Moment.model_validate(_call_service(service.moment, moment_id))

    @mcp.tool()
    def get_transcript(
        asset_id: Annotated[str, Field(description="Asset id whose transcript to read.")],
        start_s: Annotated[
            float | None,
            Field(description="Range start in seconds; defaults to 0."),
        ] = None,
        end_s: Annotated[
            float | None,
            Field(description="Range end in seconds; defaults to the asset duration."),
        ] = None,
    ) -> Transcript:
        """Read the transcript segments overlapping a range, with word timestamps.

        Quote speech exactly: every word carries absolute start and end seconds.
        """
        payload = _call_service(service.transcript, asset_id, start_s=start_s, end_s=end_s)
        return Transcript.model_validate(payload)

    @mcp.tool()
    def list_assets() -> AssetList:
        """List every asset in the index with duration, fps, codec, and proxy URL.

        Call this first to learn which asset ids the other tools accept.
        """
        return AssetList.model_validate(_call_service(service.list_assets))

    return mcp


def _call_service(operation: Callable[..., dict], *args: object, **kwargs: object) -> dict:
    """Run a service read, turning missing-index and unknown-id errors into tool errors."""
    try:
        return operation(*args, **kwargs)
    except (NotFoundError, IngestError) as exc:
        raise ToolError(str(exc)) from exc
