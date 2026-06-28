"""WebUI backend: FastAPI app and entry point.

Run with::

    python -m webui.backend.main --host 127.0.0.1 --port 8765

Or via Makefile::

    make webui        # production (serves built frontend)
    make webui-dev    # development (frontend via Vite dev server)
"""

from __future__ import annotations

import sys
from pathlib import Path

import click
from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from webui.backend import data

app = FastAPI(
    title="eval-pdf-extract WebUI",
    description="Read-only browser for benchmark results.",
    version="0.1.0",
)


# --------------------------------------------------------------------------- #
# API endpoints
# --------------------------------------------------------------------------- #


@app.get("/api/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/api/runs")
def list_runs() -> list[dict[str, object]]:
    """List all available runs."""
    return data.list_runs()


@app.get("/api/runs/{run_id}")
def get_run(run_id: str) -> dict[str, object]:
    """Get a single run's metadata."""
    result = data.get_run(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return result


@app.get("/api/runs/{run_id}/scores")
def get_run_scores(run_id: str) -> list[dict[str, object]]:
    """Get all raw scores for a run."""
    if data.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return data.get_run_scores(run_id)


@app.get("/api/runs/{run_id}/leaderboard")
def get_run_leaderboard(run_id: str) -> list[dict[str, object]]:
    """Get aggregated leaderboard for a run."""
    if data.get_run(run_id) is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return data.get_run_leaderboard(run_id)


@app.get("/api/adapters")
def list_adapters() -> list[dict[str, object]]:
    """List all adapters from registry.json."""
    return data.list_adapters()


@app.get("/api/adapters/{adapter_id}")
def get_adapter(adapter_id: str) -> dict[str, object]:
    """Get a single adapter's info and fixture-level scores across all runs."""
    result = data.get_adapter(adapter_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Adapter '{adapter_id}' not found")
    return result


@app.get("/api/fixtures")
def list_fixtures() -> list[dict[str, object]]:
    """List all fixtures from manifest.json."""
    return data.list_fixtures()


@app.get("/api/fixtures/{fixture_id}")
def get_fixture(fixture_id: str) -> dict[str, object]:
    """Get a single fixture's info, expected.json, and adapter results."""
    result = data.get_fixture(fixture_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Fixture '{fixture_id}' not found")
    return result


@app.get("/api/compare")
def get_compare(
    run_id: str = Query(..., description="Run ID to compare within"),
    fixtures: str = Query(..., description="Comma-separated fixture IDs"),
    adapters: str = Query(..., description="Comma-separated adapter IDs"),
) -> dict[str, object]:
    """Get comparison data for given run, fixtures, and adapters."""
    fixture_ids = [f.strip() for f in fixtures.split(",") if f.strip()]
    adapter_ids = [a.strip() for a in adapters.split(",") if a.strip()]
    if not fixture_ids or not adapter_ids:
        raise HTTPException(
            status_code=400,
            detail="Both 'fixtures' and 'adapters' must be non-empty",
        )
    compare_data = data.get_compare_data(run_id, fixture_ids, adapter_ids)
    if compare_data is None:
        raise HTTPException(status_code=404, detail=f"Run '{run_id}' not found")
    return compare_data


# --------------------------------------------------------------------------- #
# Static frontend serving (production mode)
# --------------------------------------------------------------------------- #

_frontend_dist = Path(__file__).resolve().parents[3] / "webui" / "frontend" / "dist"

if _frontend_dist.exists():
    app.mount("/assets", StaticFiles(directory=str(_frontend_dist / "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str) -> FileResponse:
        """Serve the React SPA — fallback to index.html for client-side routing."""
        if full_path.startswith("api/"):
            raise HTTPException(status_code=404, detail=f"Unknown API endpoint: /{full_path}")
        index = _frontend_dist / "index.html"
        return FileResponse(str(index))
else:

    @app.get("/")
    def index() -> dict[str, str]:
        """Root endpoint — frontend not built yet."""
        return {
            "message": "eval-pdf-extract WebUI",
            "docs": "/docs",
            "health": "/api/health",
            "note": "Frontend not built. Run: cd webui/frontend && npm run build",
        }


# --------------------------------------------------------------------------- #
# CLI entry point
# --------------------------------------------------------------------------- #


@click.command()
@click.option("--host", default="127.0.0.1", show_default=True, help="Bind host.")
@click.option("--port", default=8765, show_default=True, type=int, help="Bind port.")
def main(host: str, port: int) -> None:
    """Start the WebUI server."""
    try:
        import uvicorn
    except ImportError:
        click.echo("ERROR: uvicorn not installed. Run: uv sync --extra webui", err=True)
        sys.exit(2)
    click.echo(f"Starting WebUI on http://{host}:{port}", err=True)
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    main()
