# middleware/rate_limiter.py - Rate Limiting Middleware
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

class RateLimitMiddleware(BaseHTTPMiddleware):
    """Rate limiting middleware."""
    
    def __init__(self, app, security_service: SecurityService):
        super().__init__(app)
        self.security_service = security_service
    
    async def dispatch(self, request: Request, call_next) -> Response:
        # Determine endpoint type
        endpoint_type = self._get_endpoint_type(request.url.path)
        
        # Check rate limit
        if self.security_service.is_rate_limited(request, endpoint_type):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded. Please try again later."
            )
        
        # Continue with request
        response = await call_next(request)
        return response
    
    def _get_endpoint_type(self, path: str) -> str:
        """Determine endpoint type from path."""
        if '/upload' in path or 'photos' in path:
            return 'upload'
        elif '/process' in path or '/batch' in path:
            return 'process'
        elif path.endswith('/'):
            return 'list'
        else:
            return 'detail'

# middleware/content_security.py - Content Security Policy
class ContentSecurityMiddleware(BaseHTTPMiddleware):
    """Add security headers to responses."""
    
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        
        # Add security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; "
            "img-src 'self' data: https:; "
            "script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; "
            "connect-src 'self' https:; "
            "frame-ancestors 'none';"
        )
        
        return response

# routes/security_endpoints.py - Security-related endpoints
from fastapi import APIRouter, Depends, HTTPException, Request
from core.models import UserData
from core.dependencies import get_current_user

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