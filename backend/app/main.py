"""FlowSplit FastAPI Main Application.

Capacity-Aware, AI-Powered Geospatial Routing Backend.
"""

import sys
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

# Ensure workspace root is always on sys.path
root_dir = str(Path(__file__).resolve().parents[2])
if root_dir not in sys.path:
    sys.path.insert(0, root_dir)

from backend.app.config import settings
from backend.app.db.session import init_db
from backend.app.api import health, config_api, routes, roads, simulation_api

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("flowsplit")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown hooks."""
    logger.info("Initializing FlowSplit database and cache...")
    await init_db()
    logger.info("FlowSplit database tables initialized successfully.")
    yield
    logger.info("FlowSplit application shutting down.")


app = FastAPI(
    title="FlowSplit Routing Engine API",
    description="Full-Stack AI-Powered, Capacity-Aware Routing System mitigating side-street gridlock.",
    version="1.0.0",
    lifespan=lifespan,
)

# Cross-Origin Resource Sharing (CORS)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global safe exception handler: never exposes secret credentials or raw tracebacks
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error("Unhandled exception at %s %s: %s", request.method, request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "InternalServerError",
            "message": "An unexpected error occurred while processing the geospatial routing request.",
            "path": request.url.path,
        },
    )

# Include API routers
app.include_router(health.router)
app.include_router(config_api.router)
app.include_router(routes.router)
app.include_router(roads.router)
app.include_router(simulation_api.router)

# Mount frontend static directory if exists
frontend_dir = Path(__file__).resolve().parent.parent.parent / "frontend"
if frontend_dir.exists():
    app.mount("/", StaticFiles(directory=str(frontend_dir), html=True), name="frontend")
