"""Auth tests — OTP, sessions, RBAC. Phase 0 acceptance gate."""
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from esb.auth.otp import _hash_code, _generate_code


class TestOTPGeneration:
    def test_code_is_six_digits(self):
        for _ in range(20):
            code = _generate_code()
            assert len(code) == 6
            assert code.isdigit()

    def test_code_hash_is_sha256(self):
        code = "123456"
        h = _hash_code(code)
        assert h == hashlib.sha256(b"123456").hexdigest()
        assert len(h) == 64

    def test_different_codes_different_hashes(self):
        codes = {_generate_code() for _ in range(100)}
        hashes = {_hash_code(c) for c in codes}
        assert len(codes) == len(hashes)


class TestSessionTokens:
    def test_token_is_urlsafe_32_bytes(self):
        import secrets
        token = secrets.token_urlsafe(32)
        # urlsafe base64 of 32 bytes is 43 chars
        assert len(token) >= 43

    def test_token_hash_is_sha256(self):
        import secrets
        from esb.auth.sessions import _hash_token
        token = secrets.token_urlsafe(32)
        h = _hash_token(token)
        assert len(h) == 64
        assert h == hashlib.sha256(token.encode()).hexdigest()


class TestRBAC:
    def test_auth_context_has_role(self):
        from esb.auth.rbac import AuthContext
        from esb.models.user import RoleType
        ctx = AuthContext(
            person_id=uuid4(),
            roles={RoleType.practitioner_manager},
            session_id=uuid4(),
            is_step_up=False,
        )
        assert ctx.has_role(RoleType.practitioner_manager) is True
        assert ctx.has_role(RoleType.superuser) is False

    def test_step_up_required_raises(self):
        from fastapi import HTTPException
        from esb.auth.rbac import AuthContext
        from esb.models.user import RoleType
        ctx = AuthContext(
            person_id=uuid4(),
            roles={RoleType.business_manager},
            session_id=uuid4(),
            is_step_up=False,
        )
        with pytest.raises(HTTPException) as exc:
            ctx.require_step_up()
        assert exc.value.status_code == 403

    def test_step_up_ok_when_elevated(self):
        from esb.auth.rbac import AuthContext
        from esb.models.user import RoleType
        ctx = AuthContext(
            person_id=uuid4(),
            roles={RoleType.business_manager},
            session_id=uuid4(),
            is_step_up=True,
        )
        ctx.require_step_up()  # should not raise
