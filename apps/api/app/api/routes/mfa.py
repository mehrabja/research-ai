from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user
from app.core.mfa_exceptions import MFAAlreadyEnabled, MFAInvalid
from app.db.models.user import User
from app.db.session import get_db
from app.schemas.mfa import (
    MFADisableRequest,
    MFASetupResponse,
    MFAStatusResponse,
    MFAVerifyRequest,
)
from app.services import mfa as mfa_service
from app.services.audit import emit_audit
from app.services.auth import revoke_all_sessions

router = APIRouter(prefix="/auth/mfa", tags=["mfa"])


@router.get("", response_model=MFAStatusResponse)
def mfa_status(
    current_user: User = Depends(get_current_user),
) -> MFAStatusResponse:
    hashes = current_user.mfa_recovery_code_hashes or []
    return MFAStatusResponse(
        enabled=bool(current_user.mfa_enabled),
        recovery_codes_remaining=len(hashes),
    )


@router.post("/setup", response_model=MFASetupResponse)
def setup_mfa(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFASetupResponse:
    if current_user.mfa_enabled:
        raise MFAAlreadyEnabled()
    secret = mfa_service.generate_secret()
    codes = mfa_service.generate_recovery_codes()
    current_user.mfa_secret = mfa_service.encrypt_secret(secret)
    current_user.mfa_recovery_code_hashes = mfa_service.hash_recovery_codes(codes)
    db.commit()
    return MFASetupResponse(
        secret=secret,
        provisioning_uri=mfa_service.provisioning_uri(secret, current_user.email),
        recovery_codes=codes,
    )


@router.post("/enable", response_model=MFAStatusResponse)
def enable_mfa(
    body: MFAVerifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFAStatusResponse:
    if not mfa_service.verify_encrypted_code(current_user.mfa_secret, body.code):
        raise MFAInvalid()
    current_user.mfa_enabled = True
    current_user.security_version += 1
    revoke_all_sessions(db, user_id=current_user.id)
    emit_audit(
        "MFA_ENABLED",
        db=db,
        user_id=str(current_user.id),
        resource_type="mfa",
        reason="mfa_enabled",
        category="authentication",
    )
    db.commit()
    return MFAStatusResponse(
        enabled=True,
        recovery_codes_remaining=len(current_user.mfa_recovery_code_hashes or []),
    )


@router.post("/disable", response_model=MFAStatusResponse)
def disable_mfa(
    body: MFADisableRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> MFAStatusResponse:
    valid_totp = mfa_service.verify_encrypted_code(
        current_user.mfa_secret,
        body.code,
    )
    if valid_totp:
        current_user.mfa_enabled = False
    else:
        valid_recovery, remaining = mfa_service.consume_recovery_code(
            list(current_user.mfa_recovery_code_hashes or []),
            body.code,
        )
        if not valid_recovery:
            raise MFAInvalid()
        current_user.mfa_recovery_code_hashes = remaining
        current_user.mfa_enabled = False
    current_user.security_version += 1
    revoke_all_sessions(db, user_id=current_user.id)
    emit_audit(
        "MFA_DISABLED",
        db=db,
        user_id=str(current_user.id),
        resource_type="mfa",
        reason="mfa_disabled",
        category="authentication",
    )
    current_user.mfa_secret = None
    current_user.mfa_recovery_code_hashes = None
    db.commit()
    return MFAStatusResponse(enabled=False, recovery_codes_remaining=0)
