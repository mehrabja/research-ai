import uuid

from pydantic import BaseModel


class HumanizationEnqueueRequest(BaseModel):
    version_id: uuid.UUID
    detection_run_id: uuid.UUID
    policy_version: str | None = None
