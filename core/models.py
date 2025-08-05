from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# --- Temel Veri Modelleri (Pydantic) ---

class UserData(BaseModel):
    """Firestore'daki ve token içindeki kullanıcı verilerini temsil eden model."""
    uid: str
    # DEĞİŞİKLİK: Misafirlerin e-postası olmayacağı için bu alan opsiyonel hale getirildi.
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    avatar: Optional[str] = None
    subscription_plan: str = "free"
    is_guest: Optional[bool] = False

# --- API Yanıt Modelleri ---

class UserResponse(BaseModel):
    """Client'a döndürülecek kullanıcı bilgileri."""
    uid: str
    name: Optional[str] = "New User"
    # DEĞİŞİKLİK: Misafirlerin e-postası olmayacağı için bu alan opsiyonel hale getirildi.
    email: Optional[EmailStr] = None
    subscriptionPlan: str = Field(..., alias="subscription_plan")
    isGuest: Optional[bool] = Field(False, alias="is_guest")

    class Config:
        populate_by_name = True
        from_attributes = True # Pydantic v2'de `orm_mode` yerine kullanılır

class TokenResponse(BaseModel):
    """Login ve register sonrası dönen token ve kullanıcı bilgisi."""
    user: UserResponse
    access_token: str
    token_type: str = "bearer"

# --- API İstek Modelleri ---

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None