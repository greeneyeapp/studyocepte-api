# api/main.py (Refaktör Edilmiş Nihai Hali)

import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
from loguru import logger

# --- Temel servisleri import et ---
from core.firebase_config import db # Hala user check için gerekli
from core.config import settings

# --- İhtiyaç duyulan Rotaları import et ---
from routes import auth, image_processing

# Loglama yapılandırması
logger.add("file.log", rotation="500 MB", compression="zip", format="{time} {level} {message}", serialize=True, level="INFO")
logger.info("Stüdyo Cepte - Basit API başlatılıyor...")

app = FastAPI(
    title="Stüdyo Cepte - Basit API",
    description="Bu API sadece kullanıcı kimlik doğrulama ve arka plan temizleme hizmeti sunar.",
    version="2.0.0"
)

# CORS ayarları (değişiklik yok)
origins = [
    "http://localhost",
    "http://localhost:8081",
    "http://192.168.1.10:8000",
    "http://192.168.1.10:19000",
    "exp://192.168.1.10:19000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Global Hata İşleyicileri (değişiklik yok) ---
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

# --- Router'ları ana uygulamaya dahil et ---
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(image_processing.router, prefix="/image", tags=["Image Processing"])


@app.get("/")
def read_root():
    logger.info("Ana kök route'a istek geldi.")
    return {
        "message": "Stüdyo Cepte API v2.0'a hoş geldiniz!",
        "version": "2.0.0",
        "available_services": {
            "/auth": "Kullanıcı kayıt, giriş ve profil işlemleri.",
            "/image/remove-background": "POST metodu ile gönderilen fotoğrafın arka planını temizler.",
            "/docs": "API dokümantasyonu."
        }
    }

@app.get("/health")
async def health_check():
    """Basit sağlık kontrolü endpoint'i."""
    try:
        # Firestore'a basit bir erişim denemesi ile bağlantıyı kontrol et
        db.collection('users').limit(1).get()
        db_status = "ok"
    except Exception as e:
        logger.error(f"Sağlık kontrolü sırasında veritabanı hatası: {e}")
        db_status = "error"

    return {
        "status": "healthy",
        "version": "2.0.0",
        "services": {
            "database_connection": db_status
        }
    }

if __name__ == "__main__":
    service_account_path = "serviceAccountKey.json"
    if not os.path.exists(service_account_path):
        logger.error(f"{service_account_path} dosyası bulunamadı. Lütfen Firebase hizmet anahtarınızı projeye ekleyin.")
    
    if settings.SECRET_KEY == "supersecretkey":
        logger.warning("UYARI: SECRET_KEY güvenli bir değerle değiştirilmelidir!")

    uvicorn.run(app, host="0.0.0.0", port=8000)