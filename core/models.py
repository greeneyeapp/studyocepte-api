# studyocepte-api/core/models.py
from pydantic import BaseModel, EmailStr, Field
from datetime import datetime
from typing import List, Optional, Dict, Any

# --- Temel Veri Modelleri (Pydantic) ---

class UserData(BaseModel):
    """Firestore'daki ve token içindeki kullanıcı verilerini temsil eden model."""
    uid: str
    email: EmailStr
    name: Optional[str] = None
    avatar: Optional[str] = None
    subscription_plan: str = "free"

# --- API Yanıt (Response) Modelleri ---

class UserResponse(BaseModel):
    """Client'a döndürülecek kullanıcı bilgileri."""
    id: str = Field(..., alias="uid") # uid'yi id olarak map et
    name: Optional[str] = "New User"
    email: EmailStr
    subscriptionPlan: str = Field(..., alias="subscription_plan")

    class Config:
        populate_by_name = True # alias'ların çalışması için gerekli
        from_attributes = True    # Dictionaries'dan Pydantic modeline dönüşümü sağlar

class TokenResponse(BaseModel):
    """Login ve register sonrası dönen token ve kullanıcı bilgisi."""
    user: UserResponse
    access_token: str
    token_type: str = "bearer"

class ProjectBase(BaseModel):
    """Tüm proje yanıtlarında ortak olan temel alanlar."""
    id: str
    name: str
    createdAt: datetime
    updatedAt: datetime
    status: Optional[str] = "processing"
    
    class Config:
        from_attributes = True

class ProjectListResponse(ProjectBase):
    """Ana sayfadaki proje listesi için hafif model."""
    thumbnailUrl: Optional[str] = ""

class ProjectDetailResponse(ProjectListResponse):
    """Tek bir projenin tüm detayları için tam model."""
    # DEĞİŞİKLİK: 'originalImageUrl' yerine 'processedImageUrl' kullanılacak
    processedImageUrl: Optional[str] = "" 
    editorSettings: Optional[Dict] = {}
    
class BackgroundResponse(BaseModel):
    id: str
    name: str
    thumbnailUrl: str
    fullUrl: str

# --- API İstek (Request) Modelleri ---

class EditorSettingsRequest(BaseModel):
    backgroundId: str
    shadow: float
    lighting: float
    brightness: Optional[float] = 1.0 # Varsayılan değerler eklendi
    contrast: Optional[float] = 1.0
    saturation: Optional[float] = 1.0
    hue: Optional[float] = 0.0
    sepia: Optional[float] = 0.0
    # İleride eklenecek diğer filtreler için:
    # filterName: Optional[str] = None

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None