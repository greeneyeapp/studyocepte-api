# studyocepte-api/core/dependencies.py
from typing import Optional
from fastapi import Header, HTTPException, status
from core.firebase_config import db
from core.models import UserData
from jose import jwt, JWTError
from datetime import datetime, timedelta
from loguru import logger
from core.config import settings

# JWT token'ı doğrular ve mevcut kullanıcıyı döndürür
async def get_current_user(authorization: Optional[str] = Header(None)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Geçersiz veya eksik kimlik doğrulama tokenı.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not authorization:
        raise credentials_exception
    
    token_parts = authorization.split(" ")
    if len(token_parts) != 2 or token_parts[0].lower() != "bearer":
        raise credentials_exception
        
    token = token_parts[1]

    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
        
        user_ref = db.collection('users').document(user_id)
        user_doc = user_ref.get()

        if not user_doc.exists:
            logger.warning(f"Token geçerli ama kullanıcı Firestore'da bulunamadı: UID {user_id}")
            raise credentials_exception
        
        user_data = user_doc.to_dict()
        user_data['uid'] = user_doc.id

        # DÜZELTME: Eski UserData.from_dict() yerine Pydantic'in .model_validate() metodu kullanılıyor.
        return UserData.model_validate(user_data)
        
    except JWTError:
        logger.warning("JWT token doğrulanamadı veya süresi dolmuş.")
        raise credentials_exception
    except Exception as e:
        logger.error(f"Token doğrulama sırasında beklenmeyen hata: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sunucu hatası: {e}",
        )

# JWT oluşturma fonksiyonu (Bu fonksiyon doğru, değişiklik gerekmiyor)
def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)
    return encoded_jwt