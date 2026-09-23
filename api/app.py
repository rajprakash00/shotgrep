"""The REST layer: thin handlers over one QueryService.

Each route parses parameters, delegates to the service, and validates the
payload into the shared contract models; query logic lives in api/service.py.
Thumbnails are mounted statically from the index directory, and the MCP server
is mounted at /mcp so one process serves both surfaces from the same service.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from mcp.server.transport_security import TransportSecuritySettings
from starlette.routing import Route
from starlette.types import ASGIApp, Receive, Scope, Send

from api.contracts import Asset, AssetList, Moment, SearchResponse, Transcript
from api.mcp_server import create_mcp
from api.service import MAX_K, NotFoundError, QueryService
from pipeline.errors import IngestError
from pipeline.stages.index import INDEX_DIR

WORK_DIR_ENV = "SHOTGREP_WORK_DIR"
CORS_ORIGINS_ENV = "SHOTGREP_CORS_ORIGINS"
MCP_ALLOWED_HOSTS_ENV = "SHOTGREP_MCP_ALLOWED_HOSTS"
DEFAULT_WORK_DIR = "work"


def create_app(
    work_dir: Path | None = None,
    *,
    api_url: str | None = None,
    web_url: str | None = None,
) -> FastAPI:
    base = Path(work_dir or os.environ.get(WORK_DIR_ENV) or DEFAULT_WORK_DIR)
    service = QueryService(base / INDEX_DIR, api_url=api_url, web_url=web_url)
    mcp = create_mcp(service)
    mcp_app = mcp.streamable_http_app(streamable_http_path="/", transport_security=_mcp_transport_security())

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # A mounted app's own lifespan never runs, so the host starts the MCP
        # session manager for it.
        async with mcp.session_manager.run():
            yield

    app = FastAPI(
        title="shotgrep",
        version="0.1.0",
        description="Search video like it's text.",
        lifespan=lifespan,
    )
    app.state.service = service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(service.web_url),
        allow_methods=["GET", "POST", "DELETE"],
        allow_headers=["*"],
        expose_headers=["Mcp-Session-Id"],
    )
    app.mount(
        "/media",
        StaticFiles(directory=str(service.index_dir), check_dir=False),
        name="media",
    )

    @app.exception_handler(IngestError)
    async def ingest_error(request, exc: IngestError) -> JSONResponse:
        return JSONResponse(status_code=503, content={"detail": str(exc)})

    @app.exception_handler(NotFoundError)
    async def not_found(request, exc: NotFoundError) -> JSONResponse:
        return JSONResponse(status_code=404, content={"detail": str(exc)})

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/search")
    def search(
        q: str,
        k: int = Query(10, ge=1, le=MAX_K),
        asset: str | None = None,
        start_s: float | None = None,
        end_s: float | None = None,
    ) -> SearchResponse:
        return SearchResponse.model_validate(
            service.search(q, k=k, asset=asset, start_s=start_s, end_s=end_s)
        )

    @app.get("/assets")
    def assets() -> AssetList:
        return AssetList.model_validate(service.list_assets())

    @app.get("/moments/{moment_id}")
    def moment(moment_id: str) -> Moment:
        return Moment.model_validate(service.moment(moment_id))

    @app.get("/assets/{asset_id}")
    def asset(asset_id: str) -> Asset:
        return Asset.model_validate(service.asset(asset_id))

    @app.get("/assets/{asset_id}/transcript")
    def transcript(
        asset_id: str,
        start_s: float | None = None,
        end_s: float | None = None,
    ) -> Transcript:
        return Transcript.model_validate(
            service.transcript(asset_id, start_s=start_s, end_s=end_s)
        )

    # The MCP endpoint is /mcp; REST paths are matched first. A Route, not a
    # Mount, so the advertised path answers directly instead of 307ing to /mcp/.
    app.router.routes.append(Route("/mcp", _McpRootPath(mcp_app), name="mcp"))

    return app


class _McpRootPath:
    """Serves /mcp without a trailing-slash redirect.

    The MCP transport's route lives at "/" inside its own app; this maps the
    advertised path onto it. Mount would answer /mcp with a 307 to /mcp/.
    """

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        await self.app({**scope, "path": "/", "raw_path": b"/"}, receive, send)


def _cors_origins(web_url: str) -> list[str]:
    """The web app's origin; SHOTGREP_CORS_ORIGINS overrides for preview URLs."""
    configured = os.environ.get(CORS_ORIGINS_ENV, "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or [web_url]


def _mcp_transport_security() -> TransportSecuritySettings | None:
    """MCP over HTTP answers localhost only unless SHOTGREP_MCP_ALLOWED_HOSTS names the host."""
    hosts = [host.strip() for host in os.environ.get(MCP_ALLOWED_HOSTS_ENV, "").split(",") if host.strip()]
    return TransportSecuritySettings(allowed_hosts=hosts) if hosts else None
