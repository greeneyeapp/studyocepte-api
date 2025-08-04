# studyocepte-api/core/models.py
from pydantic import BaseModel, EmailStr, Field
from typing import Optional

# --- Temel Veri Modelleri (Pydantic) ---

class UserData(BaseModel):
    """Firestore'daki ve token içindeki kullanıcı verilerini temsil eden model."""
    uid: str
    email: EmailStr
    name: Optional[str] = None
    avatar: Optional[str] = None
    subscription_plan: str = "free"

# --- API Yanıt Modelleri ---

class UserResponse(BaseModel):
    """Client'a döndürülecek kullanıcı bilgileri."""
    id: str = Field(..., alias="uid")
    name: Optional[str] = "New User"
    email: EmailStr
    subscriptionPlan: str = Field(..., alias="subscription_plan")

    class Config:
        populate_by_name = True
        from_attributes = True

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