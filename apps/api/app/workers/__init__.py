from app.workers.registry import register_handler
from app.workers.research_plan_handlers import (
    handle_research_plan_generate,
)

register_handler(
    "research_plan_generate", handle_research_plan_generate
)
