from app.workers.academic_qa_handlers import (
    handle_academic_qa_generate,
)
from app.workers.citation_handlers import handle_citation_generate
from app.workers.knowledge_graph_handlers import (
    handle_knowledge_graph_build,
)
from app.workers.manuscript_handlers import handle_manuscript_generate
from app.workers.manuscript_humanization_handlers import (
    handle_manuscript_humanization,
)
from app.workers.manuscript_prose_handlers import (
    handle_manuscript_prose_generate,
)
from app.workers.orchestration_handlers import (
    handle_orchestration_run,
)
from app.workers.publication_handlers import (
    handle_publication_compliance,
)
from app.workers.rag_handlers import handle_advanced_rag_retrieve
from app.workers.registry import register_handler
from app.workers.research_plan_handlers import (
    handle_research_plan_generate,
)
from app.workers.section_research_handlers import (
    handle_section_research,
)
from app.workers.technical_intelligence_handlers import (
    handle_technical_intelligence,
)

register_handler(
    "research_plan_generate", handle_research_plan_generate
)
register_handler(
    "knowledge_graph_build", handle_knowledge_graph_build
)
register_handler(
    "advanced_rag_retrieve", handle_advanced_rag_retrieve
)
register_handler(
    "manuscript_generate", handle_manuscript_generate
)
register_handler(
    "section_research", handle_section_research
)
register_handler(
    "technical_intelligence", handle_technical_intelligence
)
register_handler(
    "citation_generate", handle_citation_generate
)
register_handler(
    "academic_qa_generate", handle_academic_qa_generate
)
register_handler(
    "manuscript_humanization", handle_manuscript_humanization
)
register_handler(
    "manuscript_prose_generate", handle_manuscript_prose_generate
)
register_handler(
    "publication_compliance", handle_publication_compliance
)
register_handler(
    "orchestration_run", handle_orchestration_run
)
