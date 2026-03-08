"""
main.py
─────────────────────────────────────────────────────────────────────────────
Intelli-Credit FastAPI application entry point.

Startup sequence:
  1. Initialise SQLite database (create tables if absent)
  2. Register API routers
  3. Configure CORS for React frontend
  4. Serve static outputs (generated CAM documents)

Run locally:
  uvicorn main:app --reload --port 8000
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings, OUTPUT_DIR
from database import init_db

# ── Routers (will be implemented in later steps) ───────────────────────────────
from api.ingest_routes import router as ingest_router
from api.score_routes import router as score_router
from api.cam_routes import router as cam_router
from api.research_routes import router as research_router
from api.insights_routes import router as insights_router

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


# ── Lifespan: startup / shutdown hooks ────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Run startup tasks before the first request, cleanup on shutdown."""
    logger.info("Starting %s v%s", settings.APP_NAME, settings.APP_VERSION)
    await init_db()
    logger.info("Database initialised at: %s", settings.DATABASE_URL)
    yield
    logger.info("Shutting down %s", settings.APP_NAME)


# ── App Initialisation ─────────────────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "AI-powered Credit Decisioning Engine for Indian NBFC corporate lending. "
        "Automates end-to-end Credit Appraisal Memo (CAM) preparation using "
        "multi-source data, transparent Five Cs scoring, and LLM-powered narration."
    ),
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

# ── CORS ───────────────────────────────────────────────────────────────────────

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static Files (generated CAM documents) ────────────────────────────────────

app.mount("/outputs", StaticFiles(directory=str(OUTPUT_DIR)), name="outputs")

# ── Route Registration ─────────────────────────────────────────────────────────

app.include_router(ingest_router,   prefix="/api/v1", tags=["Data Ingestor"])
app.include_router(score_router,    prefix="/api/v1", tags=["Scoring Engine"])
app.include_router(cam_router,      prefix="/api/v1", tags=["CAM Generator"])
app.include_router(research_router, prefix="/api/v1", tags=["Research Agent"])
app.include_router(insights_router, prefix="/api/v1", tags=["Insights"])


# ── Health Check ───────────────────────────────────────────────────────────────

@app.get("/api/health", tags=["System"])
async def health_check():
    """Simple liveness probe for Docker health checks."""
    return {
        "status": "healthy",
        "app": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


@app.get("/api/v1/config/public", tags=["System"])
async def public_config():
    """Return non-sensitive config values for the frontend."""
    return {
        "demo_company_name": settings.DEMO_COMPANY_NAME,
        "demo_company_cin": settings.DEMO_COMPANY_CIN,
        "score_max": settings.SCORE_MAX,
        "rbi_repo_rate": settings.RBI_REPO_RATE,
        "base_rate": settings.RBI_REPO_RATE + settings.NBFC_BASE_SPREAD,
        "risk_bands": settings.RISK_BANDS,
    }