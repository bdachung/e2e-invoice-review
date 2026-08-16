"""HTTP endpoints for the deployment's shared-password login."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, Response, status

from app.auth import COOKIE_NAME, LoginRequest, PasswordAuth, SessionResponse

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.get("/session", response_model=SessionResponse)
def session(request: Request) -> SessionResponse:
    auth: PasswordAuth = request.app.state.password_auth
    return SessionResponse(authenticated=auth.is_authenticated(request.cookies.get(COOKIE_NAME)))


@router.post("/login", status_code=status.HTTP_204_NO_CONTENT)
def login(body: LoginRequest, request: Request) -> Response:
    auth: PasswordAuth = request.app.state.password_auth
    if not auth.verify_password(body.password):
        raise HTTPException(status_code=401, detail="The password is incorrect.")
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    auth.set_session_cookie(response)
    return response


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout() -> Response:
    response = Response(status_code=status.HTTP_204_NO_CONTENT)
    PasswordAuth.clear_session_cookie(response)
    return response
