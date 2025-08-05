# main.py - Güncellenmiş ana uygulama dosyası
import uvicorn
import time
from fastapi import FastAPI, HTTPException, status, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import os
from datetime import datetime

# Core imports
from core.firebase_config import db
from core.config import settings
from core.messages import Messages, Language
from core.logging_system import api_logger, ErrorHandler, APIError, ErrorCategory

# Routes imports
from routes import auth, image_processing

# Middleware imports
from middleware.rate_limiter import RateLimitMiddleware, ContentSecurityMiddleware
from middleware.security import security_service

# Logging setup
from loguru import logger

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Request/Response logging middleware"""
    
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        
        # Get language from query params
        lang = request.query_params.get("lang", "tr")
        
        # Generate request ID
        import uuid
        request_id = str(uuid.uuid4())
        
        # Log request
        api_logger.log_request(request, request_id)
        
        try:
            response = await call_next(request)
            
            # Calculate response time
            process_time = time.time() - start_time
            
            # Log response
            api_logger.log_response(request, request_id, response.status_code, process_time)
            
            # Add request ID to response headers
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Response-Time"] = f"{process_time:.3f}s"
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            
            # Log error
            api_logger.log_error(
                error=e,
                category=ErrorCategory.SYSTEM,
                request=request,
                request_id=request_id,
                additional_context={"response_time": process_time}
            )
            
            # Return error response
            if isinstance(e, APIError):
                return ErrorHandler.create_error_response(
                    message_key=e.message_key,
                    status_code=e.status_code,
                    lang=lang,
                    error_id=request_id,
                    **e.message_params
                )
            else:
                return ErrorHandler.create_error_response(
                    message_key="server_error",
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    lang=lang,
                    error_id=request_id
                )

# Ana uygulama oluştur
logger.info("Stüdyo Cepte - Gelişmiş API başlatılıyor...")

app = FastAPI(
    title="Stüdyo Cepte - Gelişmiş API",
    description="""
    Bu API kullanıcı kimlik doğrulama ve görüntü arka plan temizleme hizmeti sunar.
    
    ## Özellikler
    - Çok dilli destek (Türkçe, İngilizce, İspanyolca)
    - Gelişmiş logging ve hata yönetimi
    - Rate limiting ve güvenlik
    - Misafir ve kayıtlı kullanıcı desteği
    - Toplu görüntü işleme
    
    ## Desteklenen Diller
    - `tr`: Türkçe (varsayılan)
    - `en`: English
    - `es`: Español
    """,
    version="2.1.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS ayarları
origins = [
    "http://localhost",
    "http://localhost:3000",
    "http://localhost:8081",
    "http://192.168.1.10:8000",
    "http://192.168.1.10:19000",
    "exp://192.168.1.10:19000",
    # Production domains buraya eklenebilir
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom middleware'leri ekle
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(ContentSecurityMiddleware)
app.add_middleware(RateLimitMiddleware, security_service=security_service)

# Global exception handlers
@app.exception_handler(APIError)
async def api_error_handler(request: Request, exc: APIError):
    """API Error handler"""
    lang = request.query_params.get("lang", "tr")
    
    return ErrorHandler.create_error_response(
        message_key=exc.message_key,
        status_code=exc.status_code,
        lang=lang,
        **exc.message_params
    )

@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP Exception handler"""
    lang = request.query_params.get("lang", "tr")
    
    # Client IP'sini al
    client_ip = api_logger.get_client_info(request)["client_ip"]
    
    logger.warning(f"HTTP Error: {exc.status_code} - {exc.detail} - URL: {request.url} - IP: {client_ip}")
    
    # Common HTTP errors için özel mesajlar
    message_key_map = {
        404: "not_found",
        401: "unauthorized",
        403: "unauthorized",
        422: "validation_error",
        429: "rate_limit_exceeded"
    }
    
    message_key = message_key_map.get(exc.status_code, "server_error")
    
    return ErrorHandler.create_error_response(
        message_key=message_key,
        status_code=exc.status_code,
        lang=lang
    )

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    lang = request.query_params.get("lang", "tr")
    
    # Generate error ID
    import uuid
    error_id = str(uuid.uuid4())
    
    # Log the error
    api_logger.log_error(
        error=exc,
        category=ErrorCategory.SYSTEM,
        request=request,
        request_id=error_id,
        additional_context={"handler": "global_exception_handler"}
    )
    
    return ErrorHandler.create_error_response(
        message_key="server_error",
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        lang=lang,
        error_id=error_id
    )

# Router'ları ekle
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(image_processing.router, prefix="/image", tags=["Image Processing"])

@app.get("/")
async def read_root(
    request: Request,
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    API ana sayfası
    
    - **lang**: Dil kodu (tr, en, es)
    """
    try:
        # Available services mesajları
        services_messages = {
            "tr": {
                "auth": "Kullanıcı kayıt, giriş ve profil işlemleri",
                "image": "Görüntü arka plan temizleme servisi",
                "docs": "API dokümantasyonu"
            },
            "en": {
                "auth": "User registration, login and profile operations",
                "image": "Image background removal service", 
                "docs": "API documentation"
            },
            "es": {
                "auth": "Registro de usuario, inicio de sesión y operaciones de perfil",
                "image": "Servicio de eliminación de fondo de imagen",
                "docs": "Documentación de la API"
            }
        }
        
        services = services_messages.get(lang, services_messages["tr"])
        
        response_data = {
            "message": Messages.get("welcome", lang),
            "version": "2.1.0",
            "language": lang,
            "available_languages": Messages.get_available_languages(),
            "available_services": {
                "/auth": services["auth"],
                "/image/remove-background": services["image"],
                "/docs": services["docs"]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
        logger.info(f"Root endpoint accessed with language: {lang}")
        return response_data
        
    except Exception as e:
        logger.error(f"Error in root endpoint: {e}")
        raise APIError(
            message_key="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            category=ErrorCategory.SYSTEM,
            lang=lang
        )

@app.get("/health")
async def health_check(
    request: Request,
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Sistem sağlık kontrolü
    
    - **lang**: Dil kodu (tr, en, es)
    """
    try:
        # Database bağlantı kontrolü
        try:
            db.collection('users').limit(1).get()
            db_status = "healthy"
            db_message = Messages.get("health_check_ok", lang)
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            db_status = "unhealthy"  
            db_message = Messages.get("database_connection_error", lang)

        # Genel sistem durumu
        overall_status = "healthy" if db_status == "healthy" else "degraded"
        
        health_data = {
            "status": overall_status,
            "version": "2.1.0",
            "language": lang,
            "timestamp": datetime.utcnow().isoformat(),
            "services": {
                "database": {
                    "status": db_status,
                    "message": db_message
                },
                "api": {
                    "status": "healthy",
                    "message": Messages.get("health_check_ok", lang)
                }
            },
            "uptime": time.time()  # Process başlangıcından itibaren
        }
        
        status_code = 200 if overall_status == "healthy" else 503
        
        logger.info(f"Health check performed: {overall_status}")
        return JSONResponse(content=health_data, status_code=status_code)
        
    except Exception as e:
        logger.error(f"Error in health check: {e}")
        
        error_health_data = {
            "status": "error",
            "version": "2.1.0", 
            "language": lang,
            "message": Messages.get("server_error", lang),
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }
        
        return JSONResponse(content=error_health_data, status_code=503)

@app.get("/languages")
async def get_supported_languages(request: Request):
    """
    Desteklenen dilleri döndürür
    """
    try:
        languages_info = {
            "supported_languages": [
                {
                    "code": "tr",
                    "name": "Türkçe",
                    "native_name": "Türkçe",
                    "default": True
                },
                {
                    "code": "en", 
                    "name": "English",
                    "native_name": "English",
                    "default": False
                },
                {
                    "code": "es",
                    "name": "Spanish", 
                    "native_name": "Español",
                    "default": False
                }
            ],
            "total_languages": 3,
            "default_language": "tr"
        }
        
        logger.info("Supported languages requested")
        return languages_info
        
    except Exception as e:
        logger.error(f"Error getting supported languages: {e}")
        raise APIError(
            message_key="server_error",
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            category=ErrorCategory.SYSTEM,
            lang="tr"
        )

if __name__ == "__main__":
    # Startup checks
    service_account_path = "serviceAccountKey.json"
    if not os.path.exists(service_account_path):
        logger.error(f"{service_account_path} dosyası bulunamadı. Firebase hizmet anahtarını projeye ekleyin.")
        exit(1)
    
    if settings.SECRET_KEY == "supersecretkey":
        logger.warning("UYARI: SECRET_KEY güvenli bir değerle değiştirilmelidir!")
    
    # Create logs directory
    os.makedirs("logs", exist_ok=True)
    
    logger.info("Stüdyo Cepte API v2.1.0 başlatılıyor...")
    logger.info(f"Desteklenen diller: {', '.join(Messages.get_available_languages())}")
    
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8000,
        log_config={
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                },
            },
            "handlers": {
                "default": {
                    "formatter": "default",
                    "class": "logging.StreamHandler",
                    "stream": "ext://sys.stdout",
                },
            },
            "root": {
                "level": "INFO",
                "handlers": ["default"],
            },
        }
    )