import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
from datetime import datetime
from loguru import logger

# Firebase config'i uygulama başlangıcında başlatmak için import edin
from core.firebase_config import db

# JWT ayarları için import et (settings objesi)
from core.config import settings

# Route dosyalarını import edin - TÜM YENİ ÖZELLİKLER DAHİL
from routes import auth, products, photos, image_processing, backgrounds
from routes import optimized_products, batch_operations, security_endpoints

# Security middleware import
from middleware.security import security_service
from middleware.rate_limiter import RateLimitMiddleware, ContentSecurityMiddleware

# Cache system import
from routes.caching import cache

# Loglama yapılandırması
logger.add("file.log", rotation="500 MB", compression="zip", format="{time} {level} {message}", serialize=True, level="INFO")
logger.info("FastAPI uygulaması başlıyor...")

app = FastAPI(
    title="Stüdyo Cepte API - Full Featured Version",
    description="Complete version with caching, security, batch operations, and performance improvements.",
    version="10.0.0"
)

# CORS ayarları
origins = [
    "http://localhost",
    "http://localhost:8081", # Expo Go'nun varsayılan portu
    "http://192.168.1.10:8000", # Kendi yerel IP'niz ve backend portunuz
    "http://192.168.1.10:19000", # Expo geliştirme sunucusu portu (genellikle HTTP)
    "exp://192.168.1.10:19000", # Expo geliştirme sunucusu portu (Expo schema)
    # Üretim ortamında frontend URL'inizi buraya ekleyin
    # "https://your-frontend-domain.com",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security middleware'leri ekle
if settings.RATE_LIMIT_ENABLED:
    app.add_middleware(RateLimitMiddleware, security_service=security_service)
    logger.info("Rate limiting enabled")

app.add_middleware(ContentSecurityMiddleware)
logger.info("Security headers enabled")

# --- Global Hata İşleyicileri ---
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request, exc: StarletteHTTPException):
    logger.warning(f"HTTP Hatası: {exc.status_code} - Detay: {exc.detail} - URL: {request.url}")
    return JSONResponse(
        status_code=exc.status_code,
        content={"message": exc.detail},
    )

@app.exception_handler(Exception)
async def global_exception_handler(request, exc: Exception):
    logger.exception(f"Beklenmeyen Sunucu Hatası: URL: {request.url}")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"message": "Beklenmeyen bir sunucu hatası oluştu."},
    )

# Router'ları ana uygulamaya dahil et - DOĞRU SIRALAMA
# 1. Temel endpoint'ler
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(backgrounds.router, prefix="/backgrounds", tags=["Backgrounds"])

# 2. Ana product/photo endpoint'leri
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(photos.router, prefix="/photos", tags=["Photos"])

# 3. Image processing
app.include_router(image_processing.router, prefix="/image", tags=["Image Processing"])

# 4. Optimized/enhanced endpoints
app.include_router(optimized_products.router, prefix="/api/v2/products", tags=["Optimized Products"])

# 5. Security endpoints
app.include_router(security_endpoints.router, prefix="/security", tags=["Security"])

# 6. Batch operations (sadece enable edilmişse)
if settings.ENABLE_BATCH_OPERATIONS:
    app.include_router(batch_operations.router, prefix="/batch", tags=["Batch Operations"])
    logger.info("Batch operations enabled")

@app.get("/")
def read_root():
    logger.info("Ana kök route'a istek geldi.")
    return {
        "message": "Stüdyo Cepte API v10'a hoş geldiniz! Full Featured version aktif.",
        "version": "10.0.0",
        "features": [
            "Cache sistemi",
            "Rate limiting", 
            "Güvenlik middlewares",
            "Batch operations",
            "Optimized endpoints",
            "Image processing",
            "Photo search optimization",
            "Export options",
            "CSRF protection"
        ],
        "endpoints": {
            "auth": "/auth - Kullanıcı işlemleri",
            "products": "/products - Ürün ve fotoğraf yönetimi",
            "photos": "/photos - Fotoğraf detay işlemleri",
            "optimized_products": "/api/v2/products - Optimized product endpoints", 
            "backgrounds": "/backgrounds - Editör arka planları",
            "image": "/image - Görüntü işleme araçları",
            "batch": "/batch - Toplu işlemler",
            "security": "/security - Güvenlik endpoints",
            "docs": "/docs - API dokümantasyonu"
        },
        "performance": {
            "cache_enabled": cache.enabled,
            "rate_limiting": settings.RATE_LIMIT_ENABLED,
            "monitoring": settings.MONITORING_ENABLED
        }
    }

@app.get("/health")
async def health_check():
    """Enhanced health check endpoint for monitoring."""
    
    health_status = {
        "status": "healthy",
        "version": "10.0.0",
        "timestamp": str(datetime.now()),
        "services": {
            "redis": cache.enabled,
            "rate_limiting": settings.RATE_LIMIT_ENABLED,
            "batch_operations": settings.ENABLE_BATCH_OPERATIONS,
            "monitoring": settings.MONITORING_ENABLED
        },
        "cache_stats": cache.get_stats() if cache.enabled else None,
        "security": {
            "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
            "max_file_size_mb": settings.MAX_FILE_SIZE_MB,
            "security_level": settings.SECURITY_LEVEL
        }
    }
    
    return health_status

@app.get("/api/stats")
async def get_api_stats():
    """API statistics endpoint."""
    try:
        # Get cache stats
        cache_stats = cache.get_stats() if cache.enabled else {"enabled": False}
        
        return {
            "cache": cache_stats,
            "security": {
                "rate_limit_enabled": settings.RATE_LIMIT_ENABLED,
                "max_requests_per_minute": settings.MAX_REQUESTS_PER_MINUTE,
                "max_file_size_mb": settings.MAX_FILE_SIZE_MB
            },
            "features": {
                "batch_operations": settings.ENABLE_BATCH_OPERATIONS,
                "monitoring": settings.MONITORING_ENABLED,
                "cdn_enabled": bool(settings.CDN_URL)
            }
        }
    except Exception as e:
        logger.error(f"Stats endpoint error: {e}")
        return {"error": "Stats unavailable"}

if __name__ == "__main__":
    service_account_path = "serviceAccountKey.json"
    if not os.path.exists(service_account_path):
        logger.warning(f"{service_account_path} dosyası bulunamadı. Firebase Admin SDK düzgün başlatılamayabilir.")
        logger.warning("Lütfen Firebase konsolundan indirdiğiniz hizmet hesabı anahtarını bu dosya adıyla projenizin ana dizinine yerleştirin.")
        logger.warning("Bu dosyanın .gitignore'a ekli olduğundan emin olun.")
    
    if settings.SECRET_KEY == "supersecretkey":
        logger.warning("SECRET_KEY ortam değişkeni ayarlanmamış veya varsayılan değerde. Üretim ortamında bunu güvenli bir değerle değiştirin!")
    
    if not settings.STORAGE_BUCKET_NAME:
        logger.warning("STORAGE_BUCKET_NAME ortam değişkeni ayarlanmamış. Lütfen .env dosyanızda kova adınızı belirtin!")

    # Initialize cache system
    if cache.enabled:
        logger.info("Cache system initialized successfully")
    else:
        logger.warning("Cache system not available - Redis connection failed")

    # Security check
    if not settings.RATE_LIMIT_ENABLED:
        logger.warning("Rate limiting is disabled - consider enabling for production")

    uvicorn.run(app, host="0.0.0.0", port=8000)