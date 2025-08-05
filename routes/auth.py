from fastapi import APIRouter, HTTPException, status, Depends, Body
from core.firebase_config import db
from core.models import UserData, UserResponse, LoginRequest, RegisterRequest, UpdateProfileRequest, TokenResponse, BaseModel
from core.dependencies import get_current_user, create_access_token
from passlib.context import CryptContext
from datetime import timedelta
import uuid
from loguru import logger

from core.config import settings

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashedPassword):
    return pwd_context.verify(plain_password, hashedPassword)

def get_password_hash(password):
    return pwd_context.hash(password)

@router.post("/register", response_model=TokenResponse)
async def register_user(request: RegisterRequest):
    logger.info(f"Yeni kullanıcı kayıt isteği: {request.email}")
    users_ref = db.collection('users')
    try:
        existing_user_query = users_ref.where('email', '==', request.email).limit(1).stream()
        if any(existing_user_query):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Bu e-posta adresi zaten kullanımda.")
        
        hashed_password = get_password_hash(request.password)
        new_user_ref = users_ref.document()
        user_uid = new_user_ref.id
        user_data_to_save = {
            "uid": user_uid, "email": request.email, "name": request.name,
            "subscription_plan": "free", "hashedPassword": hashed_password, "is_guest": False
        }
        new_user_ref.set(user_data_to_save)
        access_token = create_access_token(data={"sub": user_uid})
        user_response = UserResponse.model_validate(user_data_to_save)
        return TokenResponse(user=user_response, access_token=access_token)
    except Exception as e:
        logger.error(f"Kayıt işlemi sırasında hata: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Kayıt başarısız.")

@router.post("/login", response_model=TokenResponse)
async def login_user(request: LoginRequest):
    logger.info(f"Kullanıcı giriş isteği: {request.email}")
    try:
        users_ref = db.collection('users')
        user_query = users_ref.where('email', '==', request.email).limit(1).stream()
        user_doc = next(user_query, None)
        if not user_doc:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz e-posta veya şifre.")
        
        user_data_from_db = user_doc.to_dict()
        if user_data_from_db.get("is_guest"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Misafir hesapları şifre ile giriş yapamaz.")

        hashed_password_from_db = user_data_from_db.get("hashedPassword")
        if not hashed_password_from_db or not verify_password(request.password, hashed_password_from_db):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Geçersiz e-posta veya şifre.")
        
        user_uid = user_doc.id
        access_token = create_access_token(data={"sub": user_uid})
        user_response = UserResponse.model_validate({"uid": user_uid, **user_data_from_db})
        return TokenResponse(user=user_response, access_token=access_token)
    except Exception as e:
        logger.error(f"Giriş işlemi sırasında hata: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Giriş başarısız.")

@router.post("/guest", response_model=TokenResponse)
async def create_guest_user():
    logger.info("Yeni misafir oluşturma isteği.")
    users_ref = db.collection('users')
    try:
        guest_uuid = str(uuid.uuid4())
        guest_user_id = f"anon_{guest_uuid}"
                
        guest_data = {
            "uid": guest_user_id,
            "name": "Misafir Kullanıcı",
            "subscription_plan": "free",
            "is_guest": True
        }
        
        users_ref.document(guest_user_id).set(guest_data)
        logger.info(f"Yeni misafir kullanıcı oluşturuldu (e-postasız): {guest_user_id}")
        
        access_token = create_access_token(data={"sub": guest_user_id})
        user_response = UserResponse.model_validate(guest_data)
        return TokenResponse(user=user_response, access_token=access_token)
    except Exception as e:
        logger.error(f"Misafir oluşturma sırasında hata: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Misafir hesabı oluşturulamadı.")

# (login_existing_guest ve diğer endpoint'ler aynı, değişiklik yok)
@router.post("/guest/login", response_model=TokenResponse)
async def login_existing_guest(payload: dict = Body(...)):
    guest_id = payload.get("guest_id")
    logger.info(f"Mevcut misafir için giriş isteği: {guest_id}")
    if not guest_id or not guest_id.startswith("anon_"):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Geçersiz veya eksik misafir ID.")
    try:
        user_ref = db.collection('users').document(guest_id)
        user_doc = user_ref.get()
        if not user_doc.exists:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Misafir hesabı bulunamadı.")
        
        user_data = user_doc.to_dict()
        if not user_data.get("is_guest"):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Bu hesap bir misafir hesabı değil.")
            
        access_token = create_access_token(data={"sub": user_doc.id})
        user_response = UserResponse.model_validate({"uid": user_doc.id, **user_data})
        return TokenResponse(user=user_response, access_token=access_token)
    except Exception as e:
        logger.error(f"Mevcut misafir girişi sırasında hata: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Misafir girişi sırasında hata.")

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(current_user: UserData = Depends(get_current_user)):
    return UserResponse.model_validate(current_user)

@router.put("/profile", response_model=UserResponse)
async def update_user_profile(updated_data: UpdateProfileRequest, current_user: UserData = Depends(get_current_user)):
    user_ref = db.collection('users').document(current_user.uid)
    try:
        update_dict = updated_data.model_dump(exclude_unset=True)
        if not update_dict:
            return UserResponse.model_validate(current_user)
        user_ref.update(update_dict)
        updated_user_doc = user_ref.get()
        return UserResponse.model_validate({"uid": updated_user_doc.id, **updated_user_doc.to_dict()})
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Profil güncelleme başarısız.")