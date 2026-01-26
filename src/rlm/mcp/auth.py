"""
Authentication helpers for RLM MCP server.

Integrates with Snipara's OAuth Device Flow tokens stored at ~/.snipara/tokens.json.
This allows rlm-runtime to use Snipara authentication without manual API key setup.

Token resolution order:
1. OAuth tokens from ~/.snipara/tokens.json (set by snipara-mcp-login)
2. SNIPARA_API_KEY environment variable
3. API key from rlm.toml config
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Snipara token storage location (shared with snipara-mcp)
SNIPARA_TOKEN_DIR = Path.home() / ".snipara"
SNIPARA_TOKEN_FILE = SNIPARA_TOKEN_DIR / "tokens.json"


def load_snipara_tokens() -> dict[str, Any]:
    """
    Load Snipara OAuth tokens from shared storage.

    Returns:
        Dictionary of project_id -> token_data
    """
    if not SNIPARA_TOKEN_FILE.exists():
        return {}
    try:
        with open(SNIPARA_TOKEN_FILE) as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def get_snipara_token(project_id: str | None = None) -> dict[str, Any] | None:
    """
    Get Snipara OAuth token for a project.

    Args:
        project_id: Specific project ID, or None to get first available

    Returns:
        Token data if valid, None otherwise
    """
    tokens = load_snipara_tokens()

    if not tokens:
        return None

    # If no project_id specified, use the first available token
    if project_id is None:
        if tokens:
            project_id = next(iter(tokens.keys()))
        else:
            return None

    token_data = tokens.get(project_id)
    if not token_data:
        return None

    # Check if token is expired
    expires_at = token_data.get("expires_at")
    if expires_at:
        try:
            exp_time = datetime.fromisoformat(expires_at)
            # Handle both naive and timezone-aware datetimes
            # If exp_time is naive, assume it's UTC
            if exp_time.tzinfo is None:
                exp_time = exp_time.replace(tzinfo=timezone.utc)
            if exp_time < datetime.now(timezone.utc):
                # Token expired - try using snipara_mcp to refresh if available
                refreshed = _try_refresh_token(token_data.get("refresh_token"))
                if refreshed:
                    return refreshed
                return None
        except (ValueError, TypeError):
            pass

    return dict(token_data) if isinstance(token_data, dict) else None


def _try_refresh_token(refresh_token: str | None) -> dict[str, Any] | None:
    """
    Try to refresh token using snipara_mcp if available.

    This is a soft dependency - if snipara_mcp is not installed,
    token refresh won't happen and user needs to re-login.
    """
    if not refresh_token:
        return None

    try:
        import asyncio

        from snipara_mcp.auth import refresh_access_token
        return asyncio.run(refresh_access_token(refresh_token))
    except ImportError:
        # snipara_mcp not installed, can't refresh
        return None
    except Exception:
        return None


def get_snipara_auth(project_id: str | None = None) -> tuple[str | None, str | None]:
    """
    Get Snipara authentication credentials.

    Tries OAuth token first, then falls back to API key from environment.

    Args:
        project_id: Specific project ID, or None to auto-detect

    Returns:
        Tuple of (auth_header, project_slug)
        - auth_header: "Bearer <token>" or API key, or None
        - project_slug: Project slug from token, or from env, or None
    """
    # Try OAuth token first
    token_data = get_snipara_token(project_id)
    if token_data and token_data.get("access_token"):
        return (
            f"Bearer {token_data['access_token']}",
            token_data.get("project_slug", token_data.get("project_id")),
        )

    # Fall back to API key from environment
    api_key = os.environ.get("SNIPARA_API_KEY")
    project_slug = os.environ.get("SNIPARA_PROJECT_SLUG") or os.environ.get("SNIPARA_PROJECT_ID")

    if api_key:
        return (api_key, project_slug)

    return (None, None)


def get_auth_status() -> dict[str, Any]:
    """
    Get current authentication status.

    Returns:
        Dictionary with auth status information
    """
    tokens = load_snipara_tokens()
    api_key = os.environ.get("SNIPARA_API_KEY")

    status: dict[str, Any] = {
        "oauth_available": bool(tokens),
        "oauth_projects": [],
        "api_key_available": bool(api_key),
        "authenticated": False,
    }

    # Check OAuth tokens
    for project_id, data in tokens.items():
        project_info = {
            "project_id": project_id,
            "project_slug": data.get("project_slug", project_id),
            "valid": True,
        }

        expires_at = data.get("expires_at")
        if expires_at:
            try:
                exp_time = datetime.fromisoformat(expires_at)
                # Handle both naive and timezone-aware datetimes
                # If exp_time is naive, assume it's UTC
                if exp_time.tzinfo is None:
                    exp_time = exp_time.replace(tzinfo=timezone.utc)
                if exp_time < datetime.now(timezone.utc):
                    project_info["valid"] = False
                    project_info["status"] = "expired"
                else:
                    remaining = (exp_time - datetime.now(timezone.utc)).total_seconds()
                    project_info["expires_in_minutes"] = int(remaining / 60)
                    project_info["status"] = "valid"
            except (ValueError, TypeError):
                project_info["status"] = "unknown"

        status["oauth_projects"].append(project_info)

    # Determine overall auth status
    valid_oauth = any(p.get("valid") for p in status["oauth_projects"])
    status["authenticated"] = valid_oauth or bool(api_key)

    if valid_oauth:
        status["auth_method"] = "oauth"
    elif api_key:
        status["auth_method"] = "api_key"
    else:
        status["auth_method"] = None

    return status


def format_auth_instructions() -> str:
    """
    Get instructions for authenticating with Snipara.

    Returns:
        Human-readable instructions string
    """
    return """
Snipara Authentication Options:

1. OAuth Device Flow (Recommended):
   - Install: pip install snipara-mcp
   - Login:   snipara-mcp-login
   - Status:  snipara-mcp-status

2. API Key (Environment Variable):
   - export SNIPARA_API_KEY=rlm_...
   - export SNIPARA_PROJECT_SLUG=your-project

3. Config File (rlm.toml):
   [snipara]
   api_key = "rlm_..."
   project_slug = "your-project"
""".strip()
