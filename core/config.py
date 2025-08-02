import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Existing settings
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    STORAGE_BUCKET_NAME: str = os.getenv("STORAGE_BUCKET_NAME")
    
    # Redis Configuration
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    REDIS_HOST: str = os.getenv("REDIS_HOST", "127.0.0.1")
    REDIS_PORT: int = int(os.getenv("REDIS_PORT", 6379))
    REDIS_DB: int = int(os.getenv("REDIS_DB", 0))
    
    # Cache settings
    CACHE_TTL_SECONDS: int = int(os.getenv("CACHE_TTL_SECONDS", 900))
    CACHE_MAX_SIZE: int = int(os.getenv("CACHE_MAX_SIZE", 1000))
    
    # Security & Rate Limiting
    RATE_LIMIT_ENABLED: bool = os.getenv("RATE_LIMIT_ENABLED", "true").lower() == "true"
    MAX_REQUESTS_PER_MINUTE: int = int(os.getenv("MAX_REQUESTS_PER_MINUTE", 60))
    MAX_FILE_SIZE_MB: int = int(os.getenv("MAX_FILE_SIZE_MB", 50))
    SECURITY_LEVEL: str = os.getenv("SECURITY_LEVEL", "medium")
    
    # Background Tasks
    CELERY_BROKER_URL: str = os.getenv("CELERY_BROKER_URL", "redis://127.0.0.1:6379/1")
    CELERY_RESULT_BACKEND: str = os.getenv("CELERY_RESULT_BACKEND", "redis://127.0.0.1:6379/1")
    ENABLE_BATCH_OPERATIONS: bool = os.getenv("ENABLE_BATCH_OPERATIONS", "true").lower() == "true"
    
    # Monitoring
    MONITORING_ENABLED: bool = os.getenv("MONITORING_ENABLED", "false").lower() == "true"
    
    # CDN (optional)
    CDN_URL: str = os.getenv("CDN_URL", "")

settings = Settings()