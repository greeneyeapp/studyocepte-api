# routes/security_endpoints.py - Security-related endpoints
from fastapi import APIRouter, Depends, HTTPException, Request
import time
from loguru import logger

from core.models import UserData
from core.dependencies import get_current_user
from middleware.security import security_service

router = APIRouter()

@router.post("/csrf-token")
async def get_csrf_token(
    request: Request,
    current_user: UserData = Depends(get_current_user)
):
    """Get CSRF token for user."""
    token = security_service.generate_csrf_token(current_user.uid)
    return {"csrf_token": token}

@router.get("/security-info")
async def get_security_info(request: Request):
    """Get security information for client."""
    client_ip = security_service.get_client_ip(request)
    
    return {
        "client_ip": client_ip,
        "rate_limits": security_service.max_requests_per_minute,
        "max_file_size_mb": security_service.max_file_size / (1024 * 1024),
        "allowed_file_types": list(security_service.allowed_image_types),
        "security_features": [
            "Rate limiting",
            "File type validation",
            "XSS protection",
            "CSRF protection",
            "Content security policy"
        ]
    }

@router.post("/report-security-issue")
async def report_security_issue(
    issue_description: str,
    request: Request,
    current_user: UserData = Depends(get_current_user)
):
    """Report a security issue."""
    client_ip = security_service.get_client_ip(request)
    
    # Validate input
    is_valid, message = security_service.validate_input_data(issue_description, 2000)
    if not is_valid:
        raise HTTPException(status_code=400, detail=message)
    
    # Log security report
    logger.warning(f"Security issue reported by user {current_user.uid} from {client_ip}: {issue_description}")
    
    return {
        "message": "Security issue reported successfully",
        "reference_id": f"SEC-{int(time.time())}-{current_user.uid[:8]}"
    }

@router.get("/cache-stats")
async def get_cache_stats():
    """Get cache statistics."""
    from routes.caching import cache
    return cache.get_stats()