import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    # Üretim ortamında bu varsayılan değerler kullanılmamalıdır!
    SECRET_KEY: str = os.getenv("SECRET_KEY", "supersecretkey")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", 60))
    STORAGE_BUCKET_NAME: str = os.getenv("STORAGE_BUCKET_NAME")

settings = Settings()