"""
auth.py
────────────────────────────────────────────────────────
Sattva AI · Authentication Layer
Supabase JWT verification + Google OAuth integration
Supports: authenticated users + guest sessions
"""

from __future__ import annotations
import os, uuid, time
from typing import Optional
from fastapi import HTTPException, Header, Depends
from supabase import create_client


def _get_supabase():
    return create_client(
        os.getenv("SUPABASE_URL", ""),
        os.getenv("SUPABASE_ANON_KEY", ""),
    )


# ── GUEST SESSION ──────────────────────────────────────────────────────────────

def create_guest_token() -> dict:
    """
    Issue a short-lived guest token.
    Guest users can: use BMI calc, food search, AI chat (no persistence).
    Guest users cannot: save meals, view history, get personalised coaching.
    """
    guest_id = f"guest_{uuid.uuid4().hex[:16]}"
    expires_at = int(time.time()) + 86400  # 24 hours
    return {
        "guest_id": guest_id,
        "type": "guest",
        "expires_at": expires_at,
        "capabilities": ["bmi", "food_search", "ai_chat_stateless"],
        "upgrade_prompt": "Sign in with Google to save your meals and get personalized coaching.",
    }


# ── SUPABASE JWT VERIFICATION ──────────────────────────────────────────────────

async def verify_token(authorization: str = Header(...)) -> dict:
    """
    FastAPI dependency — verifies Supabase JWT from Authorization header.
    Usage: user = Depends(verify_token)

    Returns user dict with id, email, metadata.
    Raises 401 if token is invalid or expired.
    """
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authorization header must be 'Bearer <token>'")

    token = authorization.removeprefix("Bearer ").strip()

    # Guest token passthrough
    if token.startswith("guest_"):
        return {"id": token, "type": "guest", "email": None}

    try:
        sb = _get_supabase()
        response = sb.auth.get_user(token)
        user = response.user
        if not user:
            raise HTTPException(status_code=401, detail="Invalid or expired token")
        return {
            "id":       str(user.id),
            "email":    user.email,
            "type":     "authenticated",
            "metadata": user.user_metadata or {},
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Token verification failed: {str(e)}")


async def optional_token(authorization: Optional[str] = Header(default=None)) -> Optional[dict]:
    """
    Like verify_token but doesn't raise if header is missing.
    Use for endpoints that work for both guests and authenticated users.
    """
    if not authorization:
        return None
    try:
        return await verify_token(authorization)
    except HTTPException:
        return None


def require_authenticated(user: dict = Depends(verify_token)) -> dict:
    """Dependency that rejects guest tokens."""
    if user.get("type") == "guest":
        raise HTTPException(
            status_code=403,
            detail="This feature requires a signed-in account. Please sign in with Google.",
        )
    return user


# ── GOOGLE OAUTH HELPERS ───────────────────────────────────────────────────────

def get_google_oauth_url(redirect_url: str) -> str:
    """
    Generate Google OAuth sign-in URL via Supabase.
    Frontend should redirect user to this URL.
    """
    sb = _get_supabase()
    res = sb.auth.sign_in_with_oauth({
        "provider": "google",
        "options": {"redirect_to": redirect_url},
    })
    return res.url


def handle_oauth_callback(code: str) -> dict:
    """
    Exchange OAuth code for session after redirect.
    Returns session with access_token, refresh_token, user.
    """
    sb = _get_supabase()
    res = sb.auth.exchange_code_for_session({"auth_code": code})
    return {
        "access_token":  res.session.access_token,
        "refresh_token": res.session.refresh_token,
        "user_id":       str(res.user.id),
        "email":         res.user.email,
        "name":          res.user.user_metadata.get("full_name", ""),
        "avatar_url":    res.user.user_metadata.get("avatar_url", ""),
    }
