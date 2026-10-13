from __future__ import annotations

import hmac
import os
from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.core.security import (
    AUTH_COOKIE_NAME,
    SESSION_HOURS,
    auth_store,
    get_current_user,
    require_roles,
)


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class BootstrapRequest(BaseModel):
    bootstrap_token: str = Field(min_length=1, max_length=500)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class UserCreateRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)
    role: Literal[
        "admin", "analyst", "planner", "architect",
        "tester", "reviewer", "developer", "viewer",
    ] = "viewer"


class UserUpdateRequest(BaseModel):
    role: Literal[
        "admin", "analyst", "planner", "architect",
        "tester", "reviewer", "developer", "viewer",
    ] | None = None
    is_active: bool | None = None


def _set_session_cookie(response: Response, token: str) -> None:
    secure_default = (
        "true"
        if os.getenv("RENDER") or os.getenv("APP_ENV", "").casefold() == "production"
        else "false"
    )
    secure = os.getenv("AUTH_COOKIE_SECURE", secure_default).strip().casefold() in {
        "1", "true", "yes", "on"
    }
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=SESSION_HOURS * 60 * 60,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def _new_session(response: Response, user: dict) -> dict:
    token, _ = auth_store.create_session(user["user_id"])
    _set_session_cookie(response, token)
    return auth_store.public_user(user)


@router.get("/setup-status")
def get_setup_status() -> dict:
    configured = bool(os.getenv("AUTH_BOOTSTRAP_TOKEN", "").strip())
    needs_bootstrap = auth_store.user_count() == 0
    return {
        "needs_bootstrap": needs_bootstrap,
        "bootstrap_configured": configured if needs_bootstrap else False,
    }


@router.post("/bootstrap", status_code=status.HTTP_201_CREATED)
def bootstrap_admin(
    request: BootstrapRequest,
    response: Response,
) -> dict:
    expected_token = os.getenv("AUTH_BOOTSTRAP_TOKEN", "").strip()
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Initial account setup is disabled. Configure AUTH_BOOTSTRAP_TOKEN on the server.",
        )
    if not hmac.compare_digest(request.bootstrap_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid setup token.",
        )
    if auth_store.user_count() > 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Initial administrator already exists. Ask an administrator to create your account.",
        )

    try:
        user = auth_store.create_user(
            email=str(request.email),
            display_name=request.display_name,
            password=request.password,
            role="admin",
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    # Legacy projects without an owner are claimed only during the explicit
    # first-admin bootstrap, not by arbitrary sign-ups.
    from app.core.storage.project_store import project_store

    project_store.claim_unowned_projects(user["user_id"])
    public = _new_session(response, user)
    return {"user": public, "message": "Administrator account created."}


@router.post("/login")
def login(
    request: LoginRequest,
    response: Response,
    http_request: Request,
) -> dict:
    client_host = http_request.client.host if http_request.client else None
    identity = auth_store.login_identity(str(request.email), client_host)

    if auth_store.is_login_locked(identity):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many failed sign-in attempts. Try again in 15 minutes.",
        )

    user = auth_store.authenticate(str(request.email), request.password)
    if user is None:
        auth_store.record_login_failure(identity)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )

    auth_store.clear_login_failures(identity)
    return {"user": _new_session(response, user), "message": "Signed in."}


@router.post("/logout")
def logout(
    response: Response,
    http_request: Request,
    user: dict = Depends(get_current_user),
) -> dict:
    del user
    auth_store.revoke_session(http_request.cookies.get(AUTH_COOKIE_NAME))
    response.delete_cookie(
        key=AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        secure=(
            os.getenv("AUTH_COOKIE_SECURE", "").strip().casefold()
            in {"1", "true", "yes", "on"}
        ),
        samesite="lax",
    )
    return {"message": "Signed out."}


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)) -> dict:
    return {"user": auth_store.public_user(user)}


@router.get("/users")
def list_users(
    user: dict = Depends(require_roles("admin")),
) -> dict:
    del user
    return {"users": auth_store.list_users()}


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    request: UserCreateRequest,
    user: dict = Depends(require_roles("admin")),
) -> dict:
    del user
    try:
        created = auth_store.create_user(
            email=str(request.email),
            display_name=request.display_name,
            password=request.password,
            role=request.role,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"user": auth_store.public_user(created)}


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    request: UserUpdateRequest,
    current_user: dict = Depends(require_roles("admin")),
) -> dict:
    if user_id == current_user["user_id"] and request.is_active is False:
        raise HTTPException(
            status_code=400,
            detail="You cannot deactivate the currently signed-in administrator.",
        )
    if request.role is None and request.is_active is None:
        raise HTTPException(
            status_code=400,
            detail="Provide a role and/or active-state change.",
        )

    user = auth_store.update_user(
        user_id,
        role=request.role,
        is_active=request.is_active,
    )
    if user is None:
        raise HTTPException(status_code=404, detail="User not found.")
    return {"user": auth_store.public_user(user)}
