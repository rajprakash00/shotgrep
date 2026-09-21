"""The REST layer: thin handlers over one QueryService.

Each route parses parameters, delegates to the service, and returns its dict
unchanged; query logic lives in api/service.py. Thumbnails are mounted
statically from the index directory, and the same service interface will back
the MCP tools, so both surfaces present one result contract.
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

from api.service import NotFoundError, QueryService
from pipeline.errors import IngestError
from pipeline.stages.index import INDEX_DIR

WORK_DIR_ENV = "SHOTGREP_WORK_DIR"
CORS_ORIGINS_ENV = "SHOTGREP_CORS_ORIGINS"
DEFAULT_WORK_DIR = "work"
MAX_K = 100


def create_app(
    work_dir: Path | None = None,
    *,
    api_url: str | None = None,
    web_url: str | None = None,
) -> FastAPI:
    base = Path(work_dir or os.environ.get(WORK_DIR_ENV) or DEFAULT_WORK_DIR)
    service = QueryService(base / INDEX_DIR, api_url=api_url, web_url=web_url)
    app = FastAPI(title="shotgrep", version="0.1.0", description="Search video like it's text.")
    app.state.service = service
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(service.web_url),
        allow_methods=["GET"],
        allow_headers=["*"],
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
    ) -> dict:
        return service.search(q, k=k, asset=asset, start_s=start_s, end_s=end_s)

    @app.get("/moments/{moment_id}")
    def moment(moment_id: str) -> dict:
        return service.moment(moment_id)

    @app.get("/assets/{asset_id}")
    def asset(asset_id: str) -> dict:
        return service.asset(asset_id)

    @app.get("/assets/{asset_id}/transcript")
    def transcript(
        asset_id: str,
        start_s: float | None = None,
        end_s: float | None = None,
    ) -> dict:
        return service.transcript(asset_id, start_s=start_s, end_s=end_s)

    return app


def _cors_origins(web_url: str) -> list[str]:
    """The web app's origin; SHOTGREP_CORS_ORIGINS overrides for preview URLs."""
    configured = os.environ.get(CORS_ORIGINS_ENV, "")
    origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return origins or [web_url]
