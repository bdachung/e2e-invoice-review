"""Small shared-password authentication for the deployed demo."""

from __future__ import annotations

import hashlib
import hmac
import time
from dataclasses import dataclass

from fastapi import HTTPException, Request
from pydantic import BaseModel
from starlette.responses import JSONResponse, Response

COOKIE_NAME = "invoice_review_session"
PUBLIC_API_PATHS = {"/api/auth/login", "/api/auth/logout", "/api/auth/session"}


@dataclass(frozen=True)
class PasswordAuth:
    enabled: bool
    password: str | None
    session_secret: str | None
    session_max_age_seconds: int

    @classmethod
    def disabled(cls) -> PasswordAuth:
        return cls(False, None, None, 0)

    def validate_configuration(self) -> None:
        if self.enabled and (not self.password or not self.session_secret):
            raise RuntimeError(
                "Set APP_PASSWORD and SESSION_SECRET when AUTH_ENABLED is true."
            )

    def is_authenticated(self, token: str | None) -> bool:
        if not self.enabled:
            return True
        if not token or not self.session_secret:
            return False
        try:
            expires_at_text, signature = token.split(".", maxsplit=1)
            expires_at = int(expires_at_text)
        except (TypeError, ValueError):
            return False
        if expires_at < time.time():
            return False
        expected = self._sign(expires_at_text)
        return hmac.compare_digest(signature, expected)

    def verify_password(self, candidate: str) -> bool:
        if not self.enabled:
            return True
        return bool(self.password) and hmac.compare_digest(candidate, self.password)

    def set_session_cookie(self, response: Response) -> None:
        expires_at = str(int(time.time() + self.session_max_age_seconds))
        token = f"{expires_at}.{self._sign(expires_at)}"
        response.set_cookie(
            key=COOKIE_NAME,
            value=token,
            max_age=self.session_max_age_seconds,
            httponly=True,
            secure=True,
            samesite="lax",
            path="/",
        )

    @staticmethod
    def clear_session_cookie(response: Response) -> None:
        response.delete_cookie(COOKIE_NAME, httponly=True, secure=True, samesite="lax", path="/")

    def _sign(self, expires_at: str) -> str:
        if not self.session_secret:
            return ""
        return hmac.new(
            self.session_secret.encode("utf-8"),
            expires_at.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()


class LoginRequest(BaseModel):
    password: str


class SessionResponse(BaseModel):
    authenticated: bool


def require_authenticated_request(request: Request) -> None:
    auth: PasswordAuth = request.app.state.password_auth
    if not auth.is_authenticated(request.cookies.get(COOKIE_NAME)):
        raise HTTPException(status_code=401, detail="Sign in is required.")


def unauthorized_response() -> JSONResponse:
    return JSONResponse(status_code=401, content={"detail": "Sign in is required."})
