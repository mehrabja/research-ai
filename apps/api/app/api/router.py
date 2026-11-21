"""Aggregate API router."""
from __future__ import annotations

from fastapi import APIRouter

from app.api.routes.academic_qa import router as academic_qa_router
from app.api.routes.agent_runtime import router as agent_runtime_router
from app.api.routes.auth import router as auth_router
from app.api.routes.billing import router as billing_router
from app.api.routes.citations import router as citations_router
from app.api.routes.classification import (
    router as classification_router,
)
from app.api.routes.collaboration import (
    router as collaboration_router,
)
from app.api.routes.dashboard import router as dashboard_router
from app.api.routes.detection import router as detection_router
from app.api.routes.embeddings import router as embeddings_router
from app.api.routes.evidence import router as evidence_router
from app.api.routes.file_folders import router as file_folders_router
from app.api.routes.files import files_router
from app.api.routes.files import router as project_files_router
from app.api.routes.health import router as health_router
from app.api.routes.humanization import router as humanization_router
from app.api.routes.intelligence import router as intelligence_router
from app.api.routes.invitations import router as invitations_router
from app.api.routes.jobs import router as jobs_router
from app.api.routes.knowledge_graph import (
    router as knowledge_graph_router,
)
from app.api.routes.literature import router as literature_router
from app.api.routes.mcp_connections import router as mcp_connections_router
from app.api.routes.manuscript import router as manuscript_router
from app.api.routes.manuscript_humanization import (
    router as manuscript_humanization_router,
)
from app.api.routes.manuscript_prose import (
    router as manuscript_prose_router,
)
from app.api.routes.notifications import router as notifications_router
from app.api.routes.orchestration import (
    router as orchestration_router,
)
from app.api.routes.post_translation_humanization import (
    router as post_translation_humanization_router,
)
from app.api.routes.projects import router as projects_router
from app.api.routes.publication import router as publication_router
from app.api.routes.rag import router as rag_router
from app.api.routes.reports import router as reports_router
from app.api.routes.research_plan import (
    router as research_plan_router,
)
from app.api.routes.reviews import router as reviews_router
from app.api.routes.search import router as search_router
from app.api.routes.section_research import (
    router as section_research_router,
)
from app.api.routes.sources import router as sources_router
from app.api.routes.technical_intelligence import (
    router as technical_intelligence_router,
)
from app.api.routes.translation import router as translation_router
from app.api.routes.workspaces import router as workspaces_router

api_router = APIRouter()
api_router.include_router(projects_router)
api_router.include_router(health_router)
api_router.include_router(auth_router)
api_router.include_router(agent_runtime_router)
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
api_router.include_router(file_folders_router)
api_router.include_router(files_router)
api_router.include_router(intelligence_router)
api_router.include_router(classification_router)
api_router.include_router(literature_router)
api_router.include_router(research_plan_router)
api_router.include_router(knowledge_graph_router)
api_router.include_router(rag_router)
api_router.include_router(manuscript_router)
api_router.include_router(section_research_router)
api_router.include_router(technical_intelligence_router)
api_router.include_router(citations_router)
api_router.include_router(academic_qa_router)
api_router.include_router(manuscript_humanization_router)
api_router.include_router(manuscript_prose_router)
api_router.include_router(publication_router)
api_router.include_router(collaboration_router)
api_router.include_router(orchestration_router)
api_router.include_router(workspaces_router)
api_router.include_router(mcp_connections_router)
api_router.include_router(invitations_router)

api_router.include_router(notifications_router)

api_router.include_router(search_router)

api_router.include_router(billing_router)

api_router.include_router(evidence_router)

api_router.include_router(dashboard_router)
