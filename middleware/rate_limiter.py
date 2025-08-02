# middleware/rate_limiter.py - Rate Limiting Middleware
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from middleware.security import SecurityService  # Düzeltilmiş import path

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