import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # --- Temel Ayarlar ---
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))

    # --- Güvenlik ---
    # Rate limit artırıldı - önceki değer çok düşüktü
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", 180))  # 60'tan 180'e çıkarıldı
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", 25)) # Boyutu düşürebiliriz.

settings = Settings()