from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class TranslationCurrentResponse(BaseModel):
    run_id: uuid.UUID
    translation_version_id: uuid.UUID
    source_version_id: uuid.UUID | None
    source_lang: str
    target_lang: str
    provider: str
    status: str
    completed_at: datetime | None
    content: str
    preservation_check_status: str
    preservation_details: dict[str, Any] | None
