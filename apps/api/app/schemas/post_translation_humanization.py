from __future__ import annotations

import uuid

from pydantic import BaseModel

from app.schemas.manuscript_humanization import HumanizationRunRead


class PostTranslationHumanizationCurrentResponse(BaseModel):
    run: HumanizationRunRead
    translated_version_id: uuid.UUID | None
    output_version_id: uuid.UUID | None
