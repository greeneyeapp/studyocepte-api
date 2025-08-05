# routes/auth.py - Güncellenmiş auth routes with logging and multilang support
from fastapi import APIRouter, HTTPException, status, Depends, Body, Request, Query
from core.firebase_config import db
from core.models import UserData, UserResponse, LoginRequest, RegisterRequest, UpdateProfileRequest, TokenResponse
from core.dependencies import get_current_user, create_access_token
from core.messages import Messages, Language
from core.logging_system import api_logger, ErrorHandler, log_and_handle_error, error_context, ErrorCategory, APIError
from passlib.context import CryptContext
from datetime import timedelta
import uuid
from loguru import logger

from core.config import settings

router = APIRouter()
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

@router.post("/register", response_model=TokenResponse)
@log_and_handle_error(
    category=ErrorCategory.AUTH,
    message_key="server_error",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
)
async def register_user(
    request: Request,
    user_request: RegisterRequest,
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Yeni kullanıcı kaydı
    
    - **name**: Kullanıcı adı
    - **email**: E-posta adresi  
    - **password**: Şifre
    - **lang**: Dil kodu (tr, en, es)
    """
    with error_context(ErrorCategory.AUTH, "user_registration", request) as request_id:
        logger.bind(request_id=request_id).info(f"New user registration attempt: {user_request.email}")
        
        users_ref = db.collection('users')
        
        try:
            # E-posta kontrolü
            existing_user_query = users_ref.where('email', '==', user_request.email).limit(1).stream()
            if any(existing_user_query):
                api_logger.log_auth_event(
                    event_type="registration_failed_email_exists",
                    request=request,
                    request_id=request_id,
                    email=user_request.email,
                    success=False
                )
                raise APIError(
                    message_key="email_already_exists",
                    status_code=status.HTTP_400_BAD_REQUEST,
                    category=ErrorCategory.AUTH,
                    lang=lang
                )
            
            # Yeni kullanıcı oluştur
            hashed_password = get_password_hash(user_request.password)
            new_user_ref = users_ref.document()
            user_uid = new_user_ref.id
            
            user_data_to_save = {
                "uid": user_uid,
                "email": user_request.email,
                "name": user_request.name,
                "subscription_plan": "free",
                "hashedPassword": hashed_password,
                "is_guest": False
            }
            
            new_user_ref.set(user_data_to_save)
            
            # Token oluştur
            access_token = create_access_token(data={"sub": user_uid})
            
            # Log successful registration
            api_logger.log_auth_event(
                event_type="registration_success",
                request=request,
                request_id=request_id,
                user_id=user_uid,
                email=user_request.email,
                success=True
            )
            
            user_response = UserResponse.model_validate(user_data_to_save)
            logger.bind(request_id=request_id, user_id=user_uid).info("User registration completed successfully")
            
            return TokenResponse(user=user_response, access_token=access_token)
            
        except APIError:
            raise
        except Exception as e:
            api_logger.log_error(
                error=e,
                category=ErrorCategory.AUTH,
                request=request,
                request_id=request_id,
                additional_context={"operation": "user_registration", "email": user_request.email}
            )
            raise APIError(
                message_key="server_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.AUTH,
                lang=lang
            )

@router.post("/login", response_model=TokenResponse)
@log_and_handle_error(
    category=ErrorCategory.AUTH,
    message_key="server_error",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
)
async def login_user(
    request: Request,
    login_request: LoginRequest,
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Kullanıcı girişi
    
    - **email**: E-posta adresi
    - **password**: Şifre
    - **lang**: Dil kodu (tr, en, es)
    """
    with error_context(ErrorCategory.AUTH, "user_login", request) as request_id:
        logger.bind(request_id=request_id).info(f"User login attempt: {login_request.email}")
        
        try:
            users_ref = db.collection('users')
            user_query = users_ref.where('email', '==', login_request.email).limit(1).stream()
            user_doc = next(user_query, None)
            
            if not user_doc:
                api_logger.log_auth_event(
                    event_type="login_failed_user_not_found",
                    request=request,
                    request_id=request_id,
                    email=login_request.email,
                    success=False
                )
                raise APIError(
                    message_key="invalid_credentials",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    category=ErrorCategory.AUTH,
                    lang=lang
                )
            
            user_data_from_db = user_doc.to_dict()
            user_uid = user_doc.id
            
            # Misafir hesap kontrolü
            if user_data_from_db.get("is_guest"):
                api_logger.log_auth_event(
                    event_type="login_failed_guest_password_attempt",
                    request=request,
                    request_id=request_id,
                    user_id=user_uid,
                    email=login_request.email,
                    success=False
                )
                raise APIError(
                    message_key="guest_cannot_login_password",
                    status_code=status.HTTP_403_FORBIDDEN,
                    category=ErrorCategory.AUTH,
                    lang=lang
                )

            # Şifre kontrolü
            hashed_password_from_db = user_data_from_db.get("hashedPassword")
            if not hashed_password_from_db or not verify_password(login_request.password, hashed_password_from_db):
                api_logger.log_auth_event(
                    event_type="login_failed_invalid_password",
                    request=request,
                    request_id=request_id,
                    user_id=user_uid,
                    email=login_request.email,
                    success=False
                )
                raise APIError(
                    message_key="invalid_credentials",
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    category=ErrorCategory.AUTH,
                    lang=lang
                )
            
            # Başarılı giriş
            access_token = create_access_token(data={"sub": user_uid})
            
            api_logger.log_auth_event(
                event_type="login_success",
                request=request,
                request_id=request_id,
                user_id=user_uid,
                email=login_request.email,
                success=True
            )
            
            user_response = UserResponse.model_validate({"uid": user_uid, **user_data_from_db})
            logger.bind(request_id=request_id, user_id=user_uid).info("User login completed successfully")
            
            return TokenResponse(user=user_response, access_token=access_token)
            
        except APIError:
            raise
        except Exception as e:
            api_logger.log_error(
                error=e,
                category=ErrorCategory.AUTH,
                request=request,
                request_id=request_id,
                additional_context={"operation": "user_login", "email": login_request.email}
            )
            raise APIError(
                message_key="server_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.AUTH,
                lang=lang
            )

@router.post("/guest", response_model=TokenResponse)
@log_and_handle_error(
    category=ErrorCategory.AUTH,
    message_key="server_error",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
)
async def create_guest_user(
    request: Request,
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Misafir kullanıcı oluşturma
    
    - **lang**: Dil kodu (tr, en, es)
    """
    with error_context(ErrorCategory.AUTH, "guest_creation", request) as request_id:
        logger.bind(request_id=request_id).info("New guest user creation attempt")
        
        users_ref = db.collection('users')
        
        try:
            guest_uuid = str(uuid.uuid4())
            guest_user_id = f"anon_{guest_uuid}"
                    
            guest_data = {
                "uid": guest_user_id,
                "name": Messages.get("guest_user_name", lang) if Messages.MESSAGES.get("guest_user_name") else "Guest User",
                "subscription_plan": "free",
                "is_guest": True
            }
            
            users_ref.document(guest_user_id).set(guest_data)
            
            access_token = create_access_token(data={"sub": guest_user_id})
            
            api_logger.log_auth_event(
                event_type="guest_creation_success",
                request=request,
                request_id=request_id,
                user_id=guest_user_id,
                success=True
            )
            
            user_response = UserResponse.model_validate(guest_data)
            logger.bind(request_id=request_id, user_id=guest_user_id).info("Guest user created successfully")
            
            return TokenResponse(user=user_response, access_token=access_token)
            
        except Exception as e:
            api_logger.log_error(
                error=e,
                category=ErrorCategory.AUTH,
                request=request,
                request_id=request_id,
                additional_context={"operation": "guest_creation"}
            )
            raise APIError(
                message_key="server_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.AUTH,
                lang=lang
            )

@router.post("/guest/login", response_model=TokenResponse)
@log_and_handle_error(
    category=ErrorCategory.AUTH,
    message_key="server_error",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
)
async def login_existing_guest(
    request: Request,
    payload: dict = Body(...),
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Mevcut misafir kullanıcı girişi
    
    - **guest_id**: Misafir kullanıcı ID'si
    - **lang**: Dil kodu (tr, en, es)
    """
    guest_id = payload.get("guest_id")
    
    with error_context(ErrorCategory.AUTH, "guest_login", request) as request_id:
        logger.bind(request_id=request_id).info(f"Existing guest login attempt: {guest_id}")
        
        if not guest_id or not guest_id.startswith("anon_"):
            api_logger.log_auth_event(
                event_type="guest_login_failed_invalid_id",
                request=request,
                request_id=request_id,
                success=False
            )
            raise APIError(
                message_key="invalid_guest_id",
                status_code=status.HTTP_400_BAD_REQUEST,
                category=ErrorCategory.AUTH,
                lang=lang
            )
        
        try:
            user_ref = db.collection('users').document(guest_id)
            user_doc = user_ref.get()
            
            if not user_doc.exists:
                api_logger.log_auth_event(
                    event_type="guest_login_failed_not_found",
                    request=request,
                    request_id=request_id,
                    user_id=guest_id,
                    success=False
                )
                raise APIError(
                    message_key="guest_not_found",
                    status_code=status.HTTP_404_NOT_FOUND,
                    category=ErrorCategory.AUTH,
                    lang=lang
                )
            
            user_data = user_doc.to_dict()
            if not user_data.get("is_guest"):
                api_logger.log_auth_event(
                    event_type="guest_login_failed_not_guest_account",
                    request=request,
                    request_id=request_id,
                    user_id=guest_id,
                    success=False
                )
                raise APIError(
                    message_key="not_guest_account",
                    status_code=status.HTTP_403_FORBIDDEN,
                    category=ErrorCategory.AUTH,
                    lang=lang
                )
                
            access_token = create_access_token(data={"sub": user_doc.id})
            
            api_logger.log_auth_event(
                event_type="guest_login_success",
                request=request,
                request_id=request_id,
                user_id=guest_id,
                success=True
            )
            
            user_response = UserResponse.model_validate({"uid": user_doc.id, **user_data})
            logger.bind(request_id=request_id, user_id=guest_id).info("Guest login completed successfully")
            
            return TokenResponse(user=user_response, access_token=access_token)
            
        except APIError:
            raise
        except Exception as e:
            api_logger.log_error(
                error=e,
                category=ErrorCategory.AUTH,
                request=request,
                request_id=request_id,
                user_id=guest_id,
                additional_context={"operation": "guest_login"}
            )
            raise APIError(
                message_key="server_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.AUTH,
                lang=lang
            )

@router.get("/profile", response_model=UserResponse)
async def get_user_profile(
    request: Request,
    current_user: UserData = Depends(get_current_user),
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Kullanıcı profil bilgilerini getir
    
    - **lang**: Dil kodu (tr, en, es)
    """
    with error_context(ErrorCategory.AUTH, "get_profile", request, current_user.uid) as request_id:
        logger.bind(request_id=request_id, user_id=current_user.uid).info("User profile request")
        
        try:
            user_response = UserResponse.model_validate(current_user)
            logger.bind(request_id=request_id, user_id=current_user.uid).info("User profile retrieved successfully")
            return user_response
            
        except Exception as e:
            api_logger.log_error(
                error=e,
                category=ErrorCategory.AUTH,
                request=request,
                request_id=request_id,
                user_id=current_user.uid,
                additional_context={"operation": "get_profile"}
            )
            raise APIError(
                message_key="server_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.AUTH,
                lang=lang
            )

@router.put("/profile", response_model=UserResponse)
@log_and_handle_error(
    category=ErrorCategory.AUTH,
    message_key="server_error",
    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR
)
async def update_user_profile(
    request: Request,
    updated_data: UpdateProfileRequest,
    current_user: UserData = Depends(get_current_user),
    lang: str = Query("tr", description="Language code (tr, en, es)")
):
    """
    Kullanıcı profil güncelleme
    
    - **name**: Yeni kullanıcı adı (opsiyonel)
    - **lang**: Dil kodu (tr, en, es)
    """
    with error_context(ErrorCategory.AUTH, "update_profile", request, current_user.uid) as request_id:
        logger.bind(request_id=request_id, user_id=current_user.uid).info("User profile update request")
        
        user_ref = db.collection('users').document(current_user.uid)
        
        try:
            update_dict = updated_data.model_dump(exclude_unset=True)
            
            if not update_dict:
                logger.bind(request_id=request_id, user_id=current_user.uid).info("No changes in profile update")
                return UserResponse.model_validate(current_user)
            
            user_ref.update(update_dict)
            updated_user_doc = user_ref.get()
            
            logger.bind(request_id=request_id, user_id=current_user.uid).info(f"User profile updated successfully: {list(update_dict.keys())}")
            
            return UserResponse.model_validate({"uid": updated_user_doc.id, **updated_user_doc.to_dict()})
            
        except Exception as e:
            api_logger.log_error(
                error=e,
                category=ErrorCategory.AUTH,
                request=request,
                request_id=request_id,
                user_id=current_user.uid,
                additional_context={"operation": "update_profile", "update_fields": list(update_dict.keys()) if 'update_dict' in locals() else []}
            )
            raise APIError(
                message_key="server_error",
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                category=ErrorCategory.AUTH,
                lang=lang
            )