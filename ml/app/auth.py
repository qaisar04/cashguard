from __future__ import annotations

import hmac

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader

from app.settings import Settings

API_KEY_HEADER = "X-API-Key"
_header = APIKeyHeader(name=API_KEY_HEADER, auto_error=False)


def get_settings() -> Settings:
    from app.state import state

    return state.settings


def require_api_key(provided: str | None = Security(_header), settings: Settings = Depends(get_settings)) -> None:
    if provided is None or not hmac.compare_digest(provided.encode(), settings.api_key.encode()):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"Missing or invalid {API_KEY_HEADER}")
