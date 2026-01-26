"""Gmail OAuth2 authentication routes."""

from fastapi import APIRouter, Query
from fastapi.responses import RedirectResponse

from app.services.gmail_service import gmail_service

router = APIRouter()


@router.get("/gmail")
async def gmail_auth():
    """
    Initiate Gmail OAuth2 flow.
    Redirects to Google's authorization page.
    """
    auth_url = gmail_service.get_authorization_url()
    return RedirectResponse(url=auth_url)


@router.get("/gmail/callback")
async def gmail_callback(code: str = Query(...)):
    """
    Handle Gmail OAuth2 callback.
    
    Args:
        code: Authorization code from Google
    """
    result = await gmail_service.handle_oauth_callback(code)
    
    if result["success"]:
        # Redirect to frontend with success
        return RedirectResponse(url=f"http://localhost:5173/?gmail_auth=success&email={result['email']}")
    else:
        # Redirect to frontend with error
        return RedirectResponse(url=f"http://localhost:5173/?gmail_auth=error&message={result['error']}")


@router.get("/gmail/status")
async def gmail_status():
    """Check Gmail authentication status."""
    is_authenticated = gmail_service.is_authenticated()
    rate_stats = gmail_service.get_rate_limit_stats()
    
    return {
        "authenticated": is_authenticated,
        "rate_limits": rate_stats,
    }


@router.get("/gmail/debug")
async def gmail_debug():
    """Debug Gmail config."""
    from app.config import get_settings
    settings = get_settings()
    return {
        "client_id": settings.gmail_client_id or "EMPTY",
        "has_client_id": bool(settings.gmail_client_id),
        "redirect_uri": settings.gmail_redirect_uri,
    }
