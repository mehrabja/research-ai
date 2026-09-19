"""M18-A — Project domain (pure: no SQLAlchemy / FastAPI / httpx)."""
from __future__ import annotations

from enum import StrEnum


class ProjectStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    ARCHIVED = "archived"


ALL_PROJECT_STATUSES: tuple[str, ...] = tuple(s.value for s in ProjectStatus)

EDITABLE_PROJECT_STATUSES: frozenset[str] = frozenset(
    {ProjectStatus.DRAFT.value, ProjectStatus.ACTIVE.value}
)

_ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    ProjectStatus.DRAFT.value: frozenset(
        {ProjectStatus.ACTIVE.value, ProjectStatus.ARCHIVED.value}
    ),
    ProjectStatus.ACTIVE.value: frozenset({ProjectStatus.ARCHIVED.value}),
    ProjectStatus.ARCHIVED.value: frozenset(),  # terminal
}

_MAX_NAME_LENGTH = 200
_MAX_TEXT_LENGTH = 10_000
_MAX_LIST_ITEMS = 100
_MAX_LIST_ITEM_LENGTH = 1_000


class ProjectError(Exception): ...
class InvalidProjectPayloadError(ProjectError): ...
class InvalidProjectStatusTransitionError(ProjectError): ...


def normalize_name(value: str) -> str:
    if not isinstance(value, str):
        raise InvalidProjectPayloadError("name must be a string")
    stripped = value.strip()
    if not stripped:
        raise InvalidProjectPayloadError("name must not be empty")
    if len(stripped) > _MAX_NAME_LENGTH:
        raise InvalidProjectPayloadError(
            f"name must be <= {_MAX_NAME_LENGTH} chars"
        )
    return stripped


def normalize_optional_text(value: str | None, *, field: str) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str):
        raise InvalidProjectPayloadError(f"{field} must be a string")
    stripped = value.strip()
    if not stripped:
        return None
    if len(stripped) > _MAX_TEXT_LENGTH:
        raise InvalidProjectPayloadError(
            f"{field} must be <= {_MAX_TEXT_LENGTH} chars"
        )
    return stripped


def normalize_string_list(
    values: list[str] | tuple[str, ...] | None,
    *,
    field: str,
) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple)):
        raise InvalidProjectPayloadError(f"{field} must be a list")
    if len(values) > _MAX_LIST_ITEMS:
        raise InvalidProjectPayloadError(
            f"{field} must contain <= {_MAX_LIST_ITEMS} items"
        )
    out: list[str] = []
    for i, raw in enumerate(values):
        if not isinstance(raw, str):
            raise InvalidProjectPayloadError(f"{field}[{i}] must be a string")
        stripped = raw.strip()
        if not stripped:
            continue
        if len(stripped) > _MAX_LIST_ITEM_LENGTH:
            raise InvalidProjectPayloadError(
                f"{field}[{i}] must be <= {_MAX_LIST_ITEM_LENGTH} chars"
            )
        out.append(stripped)
    return out


def can_transition(current: str, target: str) -> bool:
    if current not in ALL_PROJECT_STATUSES or target not in ALL_PROJECT_STATUSES:
        return False
    return target in _ALLOWED_TRANSITIONS[current]


def can_attach_report(project_status: str) -> bool:
    return project_status in EDITABLE_PROJECT_STATUSES
