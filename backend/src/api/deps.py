"""Shared API dependencies (authentication, ownership checks)."""

from fastapi import HTTPException, Request

from ..auth_headers import USER_ID_HEADER, get_signed_user_id
from ..config import get_config


def get_current_user_id(request: Request) -> str:
    """Resolve the authenticated user id from request headers.

    When BACKEND_AUTH_SECRET is configured, requests must carry valid
    HMAC-signed headers. Otherwise (default self-hosted setup) the plain
    user id header from the trusted Next.js proxy is accepted.
    """
    config = get_config()
    if config.require_signed_auth:
        return get_signed_user_id(request, config)

    user_id = request.headers.get("user_id") or request.headers.get(USER_ID_HEADER)
    if not user_id:
        raise HTTPException(status_code=401, detail="User authentication required")
    return user_id
