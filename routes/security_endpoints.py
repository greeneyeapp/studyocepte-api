# routes/security_endpoints.py - Enhanced Security-related endpoints
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File
import time
from loguru import logger
from typing import List

from core.models import UserData
from core.dependencies import get_current_user
from middleware.security import security_service
from routes.caching import cache

router = APIRouter()

@router.post("/csrf-token")
async def get_csrf_token(
    request: Request,
    current_user: UserData = Depends(get_current_user)
):
    """Get CSRF token for user."""
    token = security_service.generate_csrf_token(current_user.uid)
    return {"csrf_token": token}

@router.post("/validate-csrf")
async def validate_csrf_token(
    csrf_token: str,
    current_user: UserData = Depends(get_current_user)
):
    """Validate CSRF token."""
    is_valid = security_service.validate_csrf_token(csrf_token, current_user.uid)
    return {"valid": is_valid}

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
            "Content security policy",
            "Malicious content detection"
        ]
    }

@router.post("/validate-file")
async def validate_file_security(
    file: UploadFile = File(...),
    current_user: UserData = Depends(get_current_user)
):
    """Validate file security before upload."""
    try:
        file_content = await file.read()
        is_valid, message = security_service.validate_file_security(file_content, file.filename or "unknown")
        
        if not is_valid:
            raise HTTPException(status_code=400, detail=message)
        
        return {
            "valid": True,
            "message": message,
            "file_info": {
                "filename": file.filename,
                "size": len(file_content),
                "content_type": file.content_type
            }
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File validation error: {e}")
        raise HTTPException(status_code=500, detail="File validation failed")

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

@router.get("/rate-limit-status")
async def get_rate_limit_status(request: Request):
    """Get current rate limit status for client."""
    client_ip = security_service.get_client_ip(request)
    
    # Get remaining requests for different endpoint types
    status_info = {}
    for endpoint_type, limit in security_service.max_requests_per_minute.items():
        # This is a simplified check - in real implementation you'd check Redis/memory
        status_info[endpoint_type] = {
            "limit": limit,
            "remaining": limit,  # Placeholder - implement actual counting
            "reset_time": int(time.time()) + 60
        }
    
    return {
        "client_ip": client_ip,
        "rate_limits": status_info,
        "blocked": client_ip in security_service.blocked_ips
    }

@router.get("/blocked-ips")
async def get_blocked_ips(current_user: UserData = Depends(get_current_user)):
    """Get list of blocked IPs (admin only)."""
    # In a real system, you'd check if user is admin
    return {
        "blocked_ips": list(security_service.blocked_ips),
        "total_blocked": len(security_service.blocked_ips)
    }

@router.post("/unblock-ip")
async def unblock_ip(
    ip_address: str,
    current_user: UserData = Depends(get_current_user)
):
    """Unblock an IP address (admin only)."""
    # In a real system, you'd check if user is admin
    if ip_address in security_service.blocked_ips:
        security_service.blocked_ips.remove(ip_address)
        logger.info(f"IP {ip_address} unblocked by admin {current_user.uid}")
        return {"message": f"IP {ip_address} unblocked successfully"}
    else:
        raise HTTPException(status_code=404, detail="IP address not found in blocked list")

@router.get("/cache-stats")
async def get_cache_stats():
    """Get cache statistics."""
    return cache.get_stats()