"""WebUI backend: FastAPI app and entry point.

Run with::

    python -m webui.backend.main --host 127.0.0.1 --port 8765
"""

from __future__ import annotations

import sys

import click
from fastapi import FastAPI

app = FastAPI(
    title="eval-pdf-extract WebUI",
    description="Read-only browser for benchmark results.",
    version="0.1.0",
)


@app.get("/api/health")
def health() -> dict[str, str]:
    """Health check endpoint."""
    return {"status": "ok"}


@app.get("/")
def index() -> dict[str, str]:
    """Root endpoint — redirects to API docs."""
    return {"message": "eval-pdf-extract WebUI", "docs": "/docs", "health": "/api/health"}


@app.get("/api/runs")
def list_runs() -> list[dict[str, str]]:
    """List available runs (stub)."""
    return []


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
