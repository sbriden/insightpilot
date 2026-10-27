from fastapi import APIRouter, HTTPException, Response

from app.auth import (
    ADMIN_COOKIE_NAME,
    admin_auth_enabled,
    issue_admin_token,
    password_matches,
)

router = APIRouter(prefix="/api/admin", tags=["Admin"])


@router.post("/login")
def login(payload: dict, response: Response):
    if not admin_auth_enabled():
        token = issue_admin_token()
        response.set_cookie(
            key=ADMIN_COOKIE_NAME,
            value=token,
            httponly=True,
            samesite="lax",
            secure=False,
            max_age=60 * 60 * 24 * 30,
            path="/",
        )
        return {
            "ok": True,
            "auth_required": False,
            "token": token,
        }

    password = str(payload.get("password") or "")
    if not password_matches(password):
        raise HTTPException(status_code=401, detail="Invalid password.")

    token = issue_admin_token()
    response.set_cookie(
        key=ADMIN_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="none",
        secure=True,
        max_age=60 * 60 * 24 * 30,
        path="/",
    )
    return {
        "ok": True,
        "auth_required": True,
        "token": token,
    }


@router.get("/status")
def status():
    return {"auth_required": admin_auth_enabled()}


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(ADMIN_COOKIE_NAME, path="/")
    return {"ok": True}
