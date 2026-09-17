"""Aggregate API router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.detection import router as detection_router
from app.api.routes.embeddings import router as embeddings_router
from app.api.routes.health import router as health_router
from app.api.routes.humanization import router as humanization_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.reports import router as reports_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.sources import router as sources_router

api_router = APIRouter()

api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(reports_router)
api_router.include_router(sources_router)
api_router.include_router(embeddings_router)
api_router.include_router(jobs_router)
api_router.include_router(detection_router)
api_router.include_router(humanization_router)
api_router.include_router(reviews_router)
