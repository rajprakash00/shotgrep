"""CLI search: a thin adapter over the shared query service.

The CLI, the REST API, and the MCP tools all call QueryService, so one result
contract covers every surface. This module only maps the work directory
convention to the service's index directory.
"""

from __future__ import annotations

from pathlib import Path

from api.service import QueryService
from pipeline.stages.index import INDEX_DIR


def search(work_dir: Path, query: str, *, k: int = 5) -> dict:
    return QueryService(Path(work_dir) / INDEX_DIR).search(query, k=k)
