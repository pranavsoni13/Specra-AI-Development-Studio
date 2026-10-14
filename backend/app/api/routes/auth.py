from __future__ import annotations

import hmac
import os
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field

from app.core.security import (
    AUTH_COOKIE_NAME,
    SESSION_HOURS,
    auth_store,
    get_current_user,
    require_roles,
    verify_password,
)


router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


class BootstrapRequest(BaseModel):
    bootstrap_token: str = Field(min_length=1, max_length=500)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)


class RegisterRequest(BaseModel):
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: str = Field(min_length=12, max_length=256)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


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


def _public_signup_enabled() -> bool:
    value = os.getenv("ALLOW_PUBLIC_SIGNUP", "true").strip().casefold()
    return value not in {"0", "false", "no", "off"}


def _cookie_secure() -> bool:
    secure_default = (
        "true"
        if os.getenv("RENDER") or os.getenv("APP_ENV", "").casefold() == "production"
        else "false"
    )
    return os.getenv("AUTH_COOKIE_SECURE", secure_default).strip().casefold() in {
        "1", "true", "yes", "on"
    }


def _set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        max_age=SESSION_HOURS * 60 * 60,
        httponly=True,
        secure=_cookie_secure(),
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
        "public_signup_enabled": (
            not needs_bootstrap and _public_signup_enabled()
        ),
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


@router.post("/register", status_code=status.HTTP_201_CREATED)
def register(
    request: RegisterRequest,
    http_request: Request,
) -> dict:
    if not _public_signup_enabled():
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Public registration is currently disabled. Ask a Specra administrator to create your account.",
        )
    if auth_store.user_count() == 0:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="The workspace administrator must be initialized before registration.",
        )

    client_host = http_request.client.host if http_request.client else None
    # Reuse the database-backed 5-attempt/15-minute throttle for registrations.
    # Count successful registrations as well so a single client cannot create
    # unlimited accounts in a short burst.
    throttle_identity = auth_store.login_identity("public-registration", client_host)
    if auth_store.is_login_locked(throttle_identity):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many account-creation attempts from this connection. Try again in 15 minutes.",
        )

    try:
        user = auth_store.create_user(
            email=str(request.email),
            display_name=request.display_name,
            password=request.password,
            role="viewer",
        )
    except ValueError as exc:
        auth_store.record_login_failure(throttle_identity)
        message = str(exc)
        code = 409 if "already exists" in message else 400
        raise HTTPException(status_code=code, detail=message) from exc

    auth_store.record_login_failure(throttle_identity)
    return {
        "message": (
            "Account created with Viewer access. Sign in, then ask a project "
            "administrator to add you to a project and assign your project role."
        ),
        "user": auth_store.public_user(user),
    }


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
        secure=_cookie_secure(),
        samesite="lax",
    )
    return {"message": "Signed out."}


@router.get("/me")
def get_me(user: dict = Depends(get_current_user)) -> dict:
    return {"user": auth_store.public_user(user)}


@router.post("/change-password")
def change_password(
    request: ChangePasswordRequest,
    response: Response,
    current_user: dict = Depends(get_current_user),
) -> dict:
    if not verify_password(request.current_password, current_user["password_hash"]):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Current password is incorrect.",
        )
    try:
        updated = auth_store.update_password(
            current_user["user_id"],
            request.new_password,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if updated is None:
        raise HTTPException(status_code=404, detail="Account not found.")
    public = _new_session(response, updated)
    return {"user": public, "message": "Password updated and sessions rotated."}


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
    if (
        user_id == current_user["user_id"]
        and request.role is not None
        and request.role != "admin"
    ):
        raise HTTPException(
            status_code=400,
            detail="You cannot remove your own administrator role.",
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
