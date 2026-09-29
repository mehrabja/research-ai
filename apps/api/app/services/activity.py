from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.api_token import APIToken
from app.db.models.auth_session import AuthSession
from app.db.models.oauth_account import OAuthAccount
from app.db.models.user import User


@dataclass(frozen=True)
class ActivityRecord:
    id: str
    event: str
    summary: str
    occurred_at: datetime


def list_user_activity(
    db: Session,
    *,
    user_id: uuid.UUID,
    limit: int = 50,
) -> list[ActivityRecord]:
    user = db.get(User, user_id)
    if user is None:
        return []

    records: list[ActivityRecord] = [
        ActivityRecord(
            id=f"user:{user.id}:created",
            event="account_created",
            summary="Account created",
            occurred_at=user.created_at,
        ),
    ]

    if user.email_verified_at is not None:
        records.append(
            ActivityRecord(
                id=f"user:{user.id}:email_verified",
                event="email_verified",
                summary="Email address verified",
                occurred_at=user.email_verified_at,
            )
        )

    sessions = db.execute(
        select(AuthSession)
        .where(AuthSession.user_id == user_id)
        .order_by(AuthSession.created_at.desc())
        .limit(limit)
    ).scalars()
    for session in sessions:
        records.append(
            ActivityRecord(
                id=f"session:{session.id}:created",
                event="session_created",
                summary="New sign-in session created",
                occurred_at=session.created_at,
            )
        )
        if session.revoked_at is not None:
            records.append(
                ActivityRecord(
                    id=f"session:{session.id}:revoked",
                    event="session_revoked",
                    summary="Sign-in session revoked",
                    occurred_at=session.revoked_at,
                )
            )

    tokens = db.execute(
        select(APIToken)
        .where(APIToken.user_id == user_id)
        .order_by(APIToken.created_at.desc())
        .limit(limit)
    ).scalars()
    for token in tokens:
        records.append(
            ActivityRecord(
                id=f"token:{token.id}:created",
                event="api_token_created",
                summary="Personal API token created",
                occurred_at=token.created_at,
            )
        )
        if token.revoked_at is not None:
            records.append(
                ActivityRecord(
                    id=f"token:{token.id}:revoked",
                    event="api_token_revoked",
                    summary="Personal API token revoked",
                    occurred_at=token.revoked_at,
                )
            )

    accounts = db.execute(
        select(OAuthAccount)
        .where(OAuthAccount.user_id == user_id)
        .order_by(OAuthAccount.created_at.desc())
        .limit(limit)
    ).scalars()
    for account in accounts:
        records.append(
            ActivityRecord(
                id=f"oauth:{account.id}:linked",
                event="oauth_linked",
                summary=f"{account.provider.title()} account linked",
                occurred_at=account.created_at,
            )
        )

    records.sort(key=lambda item: item.occurred_at, reverse=True)
    return records[: max(1, min(limit, 100))]
