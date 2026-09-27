from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.api_token import APITokenCreate, APITokenCreated, APITokenRead
from app.services.api_tokens import create_token, list_tokens, revoke_token

router = APIRouter(prefix="/auth/api-tokens", tags=["api-tokens"])


@router.post("", response_model=APITokenCreated, status_code=status.HTTP_201_CREATED)
def create_api_token(
    body: APITokenCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> APITokenCreated:
    row, raw = create_token(
        db,
        user_id=current_user.id,
        name=body.name,
        expires_at=body.expires_at,
    )
    db.commit()
    db.refresh(row)
    return APITokenCreated(
        id=row.id,
        name=row.name,
        token=raw,
        token_prefix=row.token_prefix,
        expires_at=row.expires_at,
    )


@router.get("", response_model=list[APITokenRead])
def list_api_tokens(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[APITokenRead]:
    return [
        APITokenRead.model_validate(row, from_attributes=True)
        for row in list_tokens(db, user_id=current_user.id)
    ]


@router.delete("/{token_id}", status_code=status.HTTP_204_NO_CONTENT)
def revoke_api_token(
    token_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> None:
    revoke_token(
        db,
        user_id=current_user.id,
        token_id=token_id,
    )
    db.commit()
