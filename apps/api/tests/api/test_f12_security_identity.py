"""F12 security identity API regression coverage."""
from __future__ import annotations

import uuid

import pyotp
from app.db.models.user import User
from app.db.session import SessionLocal
from tests._m37_api_helpers import PW, auth, client
from tests._m37_cleanup import purge_test_users


def test_mfa_disable_accepts_recovery_code_once() -> None:
    email = f"f12-mfa-{uuid.uuid4().hex[:10]}@example.com"
    register = client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": PW},
    )
    assert register.status_code == 201, register.text
    user_id = uuid.UUID(register.json()["id"])

    try:
        login = client.post(
            "/api/v1/auth/login",
            json={"email": email, "password": PW},
        )
        assert login.status_code == 200, login.text
        token = login.json()["access_token"]

        setup = client.post(
            "/api/v1/auth/mfa/setup",
            headers=auth(token),
            json={},
        )
        assert setup.status_code == 200, setup.text
        setup_body = setup.json()
        secret = setup_body["secret"]
        recovery_code = setup_body["recovery_codes"][0]

        enable = client.post(
            "/api/v1/auth/mfa/enable",
            headers=auth(token),
            json={"code": pyotp.TOTP(secret).now()},
        )
        assert enable.status_code == 200, enable.text
        assert enable.json()["enabled"] is True

        # Enabling MFA increments security_version and revokes the pre-MFA
        # session, so authenticate again using the freshly enabled TOTP.
        relogin = client.post(
            "/api/v1/auth/login",
            json={
                "email": email,
                "password": PW,
                "mfa_code": pyotp.TOTP(secret).now(),
            },
        )
        assert relogin.status_code == 200, relogin.text
        token = relogin.json()["access_token"]

        disable = client.post(
            "/api/v1/auth/mfa/disable",
            headers=auth(token),
            json={"code": recovery_code},
        )
        assert disable.status_code == 200, disable.text
        assert disable.json() == {
            "enabled": False,
            "recovery_codes_remaining": 7,
        }

        with SessionLocal() as db:
            user = db.get(User, user_id)
            assert user is not None
            assert user.mfa_enabled is False
            assert user.mfa_secret is None
            assert len(user.mfa_recovery_code_hashes or []) == 7
    finally:
        with SessionLocal() as db:
            purge_test_users(db, [user_id])
            db.commit()
