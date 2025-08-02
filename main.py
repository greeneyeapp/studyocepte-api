import uvicorn
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
import os
from loguru import logger

# Firebase config'i uygulama başlangıcında başlatmak için import edin
from core.firebase_config import db

# JWT ayarları için import et (settings objesi)
from core.config import settings

# Route dosyalarını import edin
from routes import auth, products, photos, image_processing, backgrounds

# Loglama yapılandırması
logger.add("file.log", rotation="500 MB", compression="zip", format="{time} {level} {message}", serialize=True, level="INFO")
logger.info("FastAPI uygulaması başlıyor...")

app = FastAPI(
    title="Stüdyo Cepte API - Product/Photo Yapısı",
    description="Yeni yapı: Ürünler ve fotoğraflar ayrı yönetilir. Çoklu fotoğraf desteği.",
    version="9.0.0"
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

# Router'ları ana uygulamaya dahil et
app.include_router(auth.router, prefix="/auth", tags=["Auth"])
app.include_router(products.router, prefix="/products", tags=["Products"])
app.include_router(photos.router, prefix="/photos", tags=["Photos"])
app.include_router(image_processing.router, prefix="/image", tags=["Image Processing"])
app.include_router(backgrounds.router, prefix="/backgrounds", tags=["Backgrounds"])

@app.get("/")
def read_root():
    logger.info("Ana kök route'a istek geldi.")
    return {
        "message": "Stüdyo Cepte API v9'a hoş geldiniz! Product/Photo yapısı aktif.",
        "version": "9.0.0",
        "endpoints": {
            "auth": "/auth - Kullanıcı işlemleri",
            "products": "/products - Ürün ve fotoğraf yönetimi", 
            "backgrounds": "/backgrounds - Editör arka planları",
            "image": "/image - Görüntü işleme araçları",
            "docs": "/docs - API dokümantasyonu"
        }
    }

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

    uvicorn.run(app, host="0.0.0.0", port=8000)