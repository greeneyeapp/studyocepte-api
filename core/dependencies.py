from typing import Optional
from fastapi import Header, HTTPException, status, Query
from core.firebase_config import db
from core.models import UserData
from core.messages import Messages
from jose import jwt, JWTError
from datetime import datetime, timedelta
from loguru import logger
from core.config import settings

# JWT token'ı doğrular ve mevcut kullanıcıyı döndürür
async def get_current_user(
    authorization: Optional[str] = Header(None),
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """JWT token'ı doğrular ve mevcut kullanıcıyı döndürür"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=Messages.get("auth_token_invalid", lang),
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=Messages.get("auth_token_missing", lang),
            headers={"WWW-Authenticate": "Bearer"},
        )
    
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
            logger.warning(f"Token valid but user not found in Firestore: UID {user_id}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail=Messages.get("user_not_found", lang),
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        user_data = user_doc.to_dict()
        user_data['uid'] = user_doc.id

        return UserData.model_validate(user_data)
        
    except JWTError:
        logger.warning("JWT token validation failed or expired")
        raise credentials_exception
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error during token validation: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail= Messages.get("server_error", lang),
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