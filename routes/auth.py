# studyocepte-api/routes/auth.py
from fastapi import APIRouter, HTTPException, status, Depends
from core.firebase_config import db
from core.models import UserData, UserResponse, LoginRequest, RegisterRequest, UpdateProfileRequest, TokenResponse
from core.dependencies import get_current_user, create_access_token
from passlib.context import CryptContext
from datetime import datetime, timedelta

from core.config import settings
from loguru import logger # EKSİK IMPORT EKLENDİ

router = APIRouter()

# --- Şifreleme Fonksiyonları (Senin kodundan alındı) ---
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

# --- Endpoints ---

@router.post("/register", response_model=TokenResponse)
async def register_user(request: RegisterRequest):
    logger.info(f"Yeni kullanıcı kayıt isteği: {request.email}")
    users_ref = db.collection('users')
    
    try:
        # E-postanın zaten var olup olmadığını kontrol et
        existing_user_query = users_ref.where('email', '==', request.email).limit(1).stream()
        if any(existing_user_query):
            logger.warning(f"Kayıt hatası: E-posta zaten kullanımda: {request.email}")
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu e-posta adresi zaten kullanımda.")

        hashed_password = get_password_hash(request.password)
        
        # Firestore'da yeni bir doküman oluştur
        new_user_ref = users_ref.document()
        user_uid = new_user_ref.id

        # Firestore'a kaydedilecek veri
        user_data_to_save = {
            "uid": user_uid,
            "email": request.email,
            "name": request.name,
            "avatar": f"https://i.pravatar.cc/150?u={request.email}",
            "subscription_plan": "free",
            "hashedPassword": hashed_password
        }
        
        new_user_ref.set(user_data_to_save)
        logger.info(f"Yeni kullanıcı kaydedildi: {request.email} (UID: {user_uid})")
        
        # Token oluştur
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user_uid}, expires_delta=access_token_expires
        )
        
        # Client'a döndürülecek yanıtı Pydantic modelleriyle oluştur
        user_response = UserResponse.model_validate(user_data_to_save)
        
        return TokenResponse(
            user=user_response,
            access_token=access_token
        )
    except Exception as e:
        logger.error(f"Kayıt işlemi sırasında hata oluştu: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Kayıt başarısız: Sunucu hatası."
        )


@router.post("/login", response_model=TokenResponse)
async def login_user(request: LoginRequest):
    logger.info(f"Kullanıcı giriş isteği: {request.email}")
    try:
        users_ref = db.collection('users')
        user_query = users_ref.where('email', '==', request.email).limit(1).stream()
        
        user_doc = next(user_query, None) # Sorgudan ilk sonucu al

        if not user_doc:
            logger.warning(f"Giriş hatası: Kullanıcı bulunamadı: {request.email}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz e-posta veya şifre.")
        
        user_data_from_db = user_doc.to_dict()
        hashed_password_from_db = user_data_from_db.get("hashedPassword")

        if not hashed_password_from_db or not verify_password(request.password, hashed_password_from_db):
            logger.warning(f"Giriş hatası: Geçersiz şifre: {request.email}")
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz e-posta veya şifre.")
        
        user_uid = user_doc.id
        logger.info(f"Kullanıcı başarıyla giriş yaptı: {request.email} (UID: {user_uid})")
        
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(data={"sub": user_uid}, expires_delta=access_token_expires)
        
        # DÜZELTME: `.from_dict` yerine Pydantic'in `.model_validate` metodunu kullan
        user_response = UserResponse.model_validate({"uid": user_uid, **user_data_from_db})

        return TokenResponse(
            user=user_response,
            access_token=access_token
        )
    except Exception as e:
        logger.error(f"Giriş işlemi sırasında hata oluştu: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Giriş başarısız: Sunucu hatası."
        )

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(current_user: UserData = Depends(get_current_user)):
    logger.info(f"Profil bilgileri isteği: {current_user.email}")
    return UserResponse.model_validate(current_user)

@router.put("/profile", response_model=UserResponse)
async def update_user_profile(updated_data: UpdateProfileRequest, current_user: UserData = Depends(get_current_user)):
    user_ref = db.collection('users').document(current_user.uid)
    try:
        update_dict = updated_data.model_dump(exclude_unset=True) 
        
        if not update_dict:
            # Güncellenecek bir şey yoksa mevcut kullanıcıyı döndür
            return UserResponse.model_validate(current_user)
        
        user_ref.update(update_dict) 
        logger.info(f"Kullanıcı profili güncellendi: {current_user.email} - Değişiklikler: {update_dict}")

        updated_user_doc = user_ref.get()
        updated_user_data_dict = updated_user_doc.to_dict()
        
        return UserResponse.model_validate({"uid": updated_user_doc.id, **updated_user_data_dict})
    except Exception as e:
        logger.error(f"Profil güncelleme sırasında hata oluştu: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail=f"Profil güncelleme başarısız."
        )