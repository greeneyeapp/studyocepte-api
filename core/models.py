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

# --- Editor Settings ---
class EditorSettings(BaseModel):
    """Photo editor settings model."""
    backgroundId: str = "bg1"
    shadow: float = 0.5
    lighting: float = 0.7
    brightness: Optional[float] = 1.0
    contrast: Optional[float] = 1.0
    saturation: Optional[float] = 1.0
    hue: Optional[float] = 0.0
    sepia: Optional[float] = 0.0

# --- Product Photo Models ---
class ProductPhotoBase(BaseModel):
    """Base model for product photos."""
    id: str
    productId: str
    originalImageUrl: str = Field(..., alias="rawImageUrl")  # Backend'de rawImageUrl olarak saklanıyor
    processedImageUrl: Optional[str] = ""
    thumbnailUrl: Optional[str] = ""
    status: str = "processing"  # processing, completed, failed
    editorSettings: Optional[EditorSettings] = None
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        populate_by_name = True
        from_attributes = True

class ProductPhotoDetail(ProductPhotoBase):
    """Detailed photo model with signed URLs."""
    pass

# --- Product Models ---
class ProductBase(BaseModel):
    """Base product model."""
    id: str
    name: str
    createdAt: datetime
    updatedAt: datetime
    
    class Config:
        from_attributes = True

class ProductListResponse(ProductBase):
    """Product list response with photo count and cover image."""
    photoCount: int = 0
    coverThumbnailUrl: Optional[str] = ""

class ProductDetailResponse(ProductBase):
    """Detailed product response with all photos."""
    photos: List[ProductPhotoDetail] = []

# --- API Response Models ---
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

class BackgroundResponse(BaseModel):
    """Background model for editor."""
    id: str
    name: str
    thumbnailUrl: str
    fullUrl: str

# --- API Request Models ---
class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    name: str
    email: EmailStr
    password: str

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None

class CreateProductRequest(BaseModel):
    name: str

class EditorSettingsRequest(BaseModel):
    # Enhanced adjustment settings (-100 to +100)
    exposure: Optional[int] = 0
    highlights: Optional[int] = 0
    shadows: Optional[int] = 0
    brightness: Optional[int] = 0
    contrast: Optional[int] = 0
    saturation: Optional[int] = 0
    vibrance: Optional[int] = 0 
    warmth: Optional[int] = 0
    tint: Optional[int] = 0 
    clarity: Optional[int] = 0 
    noise: Optional[int] = 0 
    vignette: Optional[int] = 0

    # Photo positioning
    photoX: Optional[float] = 0.5
    photoY: Optional[float] = 0.5
    photoScale: Optional[float] = 1.0
    photoRotation: Optional[int] = 0

    # Crop settings (eğer backend'de işlenecekse)
    cropAspectRatio: Optional[str] = 'original' 
    cropX: Optional[float] = 0
    cropY: Optional[float] = 0
    cropWidth: Optional[float] = 1
    cropHeight: Optional[float] = 1
    
    # Effect target (eğer backend'de kullanılacaksa)
    effectTarget: Optional[str] = 'photo' 

    # Legacy settings for API compatibility (eğer hala kullanılıyorsa ve frontend'den geliyorsa)
    shadow: Optional[float] = 0.5
    lighting: Optional[float] = 0.7

# --- Legacy Project Models (Backward Compatibility) ---
class ProjectBase(BaseModel):
    """Legacy project model - kept for backward compatibility."""
    id: str
    name: str
    createdAt: datetime
    updatedAt: datetime
    status: Optional[str] = "processing"
    
    class Config:
        from_attributes = True

class ProjectListResponse(ProjectBase):
    """Legacy project list response."""
    thumbnailUrl: Optional[str] = ""

class ProjectDetailResponse(ProjectListResponse):
    """Legacy project detail response."""
    processedImageUrl: Optional[str] = ""
    editorSettings: Optional[Dict] = {}