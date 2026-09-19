"""Aggregate API router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.auth import router as auth_router
from app.api.routes.classification import (
    router as classification_router,
)
from app.api.routes.detection import router as detection_router
from app.api.routes.embeddings import router as embeddings_router
from app.api.routes.files import files_router
from app.api.routes.files import router as project_files_router
from app.api.routes.health import router as health_router
from app.api.routes.humanization import router as humanization_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.post_translation_humanization import (
    router as post_translation_humanization_router,
)
from app.api.routes.projects import router as projects_router
from app.api.routes.reports import router as reports_router
from app.api.routes.reviews import router as reviews_router
from app.api.routes.sources import router as sources_router
from app.api.routes.translation import router as translation_router

api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(reports_router)
api_router.include_router(sources_router)
api_router.include_router(embeddings_router)
api_router.include_router(jobs_router)
api_router.include_router(detection_router)
api_router.include_router(humanization_router)
api_router.include_router(reviews_router)
api_router.include_router(translation_router)
api_router.include_router(post_translation_humanization_router)
api_router.include_router(project_files_router)
api_router.include_router(files_router)
api_router.include_router(intelligence_router)
api_router.include_router(classification_router)
