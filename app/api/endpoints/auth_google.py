import urllib.parse
import time
from http.client import HTTPException
from typing import Any
import httpx
from fastapi import APIRouter, Query, Request
from starlette.responses import RedirectResponse, JSONResponse

from app.core.config import settings
import secrets

# ---- In-memory stores (DEV ONLY) ----
# state -> {created_at, return_to}
_OAUTH_STATE: dict[str, dict[str, Any]] = {}

# user_key -> token payload (DEV ONLY)
# In production you will store tokens encrypted in DB.
_TOKEN_STORE: dict[str, dict[str, Any]] = {}

router = APIRouter()

def _build_google_authorize_url(*, state: str, redirect_uri: str) -> str:
    """
    Function to build a Google authorization url for Google oauth flow.
    Only collects basic information such as profile, email, and openid and access to read
    Google calendar.
    """
    # Scopes: identity + calendar read-only (the least privilege to start)
    scopes = [
        "openid",
        "email",
        "profile",
        "https://www.googleapis.com/auth/calendar.readonly",
    ]

    params = {
        "client_id": settings.google_client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,

        # Recommended for refresh tokens:
        "access_type": "offline",
        # Often needed to reliably receive refresh_token on repeated logins:
        "prompt": "consent",
    }

    return settings.google_redirect_uri + urllib.parse.urlencode(params)

def _callback_url() -> str:
    return settings.backend_base_url.rstrip("/") + "/api/auth/google/callback"

@router.get("/start")
async def google_start(return_to: str = Query(default="/")):
    """
    Redirect user to Google's OAuth consent screen.
    """
    if not settings.google_client_id or not settings.google_client_secret:
        raise HTTPException(status_code=500, detail="Google OAuth not configured")

    state = secrets.token_urlsafe(32)

    # Store state for CSRF protection + post-login redirect target
    _OAUTH_STATE[state] = {
        "created_at": time.time(),
        "return_to": return_to,
    }

    auth_url = _build_google_authorize_url(
        state=state,
        redirect_uri=_callback_url(),
    )
    return RedirectResponse(url=auth_url, status_code=302)

router.get("/callback")
async def google_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    ):
    """
    Google redirects here with ?code=...&state=...
    We verify state, exchange code for tokens, then redirect back to frontend.
    """
    if error:
        # User denied consent or Google returned an auth error
        raise HTTPException(status_code=400, detail=f"Google OAuth error: {error}")

    if not code or not state:
        # Google should return a code and state if verified
        raise HTTPException(status_code=400, detail="Missing code or state")

    state_entry = _OAUTH_STATE.pop(state, None)
    if not state_entry:
        # This is mainly for development, we should store states in db in the future.
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    # Optional: state expiration (10 minutes)
    if time.time() - float(state_entry["created_at"]) > 600:
        raise HTTPException(status_code=400, detail="State expired")

    token_url = "https://oauth2.googleapis.com/token"

    data = {
        "code": code,
        "client_id": settings.google_client_id,
        "client_secret": settings.google_client_secret,
        "redirect_uri": _callback_url(),
        "grant_type": "authorization_code",
    }

    # Asynchronously send data to Google to verify if we can access information of client
    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(token_url, data=data)

    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {resp.text}")

    token_payload = resp.json()

    # DEV ONLY: store tokens in memory keyed by something.
    # For now, we key by client IP + UA (not reliable; replace with real user/session later).
    user_key = f"{request.client.host}:{request.headers.get('user-agent', '')}"
    _TOKEN_STORE[user_key] = token_payload

    # Redirect back to frontend (recommended for OAuth)
    # You can pass a simple flag; do NOT put tokens in the URL.
    return_to = state_entry.get("return_to") or "/"
    frontend_url = settings.frontend_base_url.rstrip("/") + return_to

    # Add a simple success indicator (safe)
    sep = "&" if ("?" in frontend_url) else "?"
    return RedirectResponse(url=f"{frontend_url}{sep}oauth=success", status_code=302)

@router.get("/debug/token")
async def debug_token(request: Request):
    """
    DEV ONLY: returns the last token payload stored for this requester.
    Do NOT ship this in prod.
    """
    user_key = f"{request.client.host}:{request.headers.get('user-agent','')}"
    payload = _TOKEN_STORE.get(user_key)
    if not payload:
        return JSONResponse({"has_token": False})
    # Avoid returning refresh_token in a real app, even in dev.
    safe = {k: v for k, v in payload.items() if k != "refresh_token"}
    return JSONResponse({"has_token": True, "token": safe})