from fastapi import APIRouter
from typing import List
from core.models import BackgroundResponse

from loguru import logger # loguru import edildi

router = APIRouter()

STATIC_BACKGROUNDS = [
  {"id": "bg1", "name": "Studio White", "thumbnailUrl": "https://images.pexels.com/photos/1762851/pexels-photo-1762851.jpeg?auto=compress&cs=tinysrgb&w=200", "fullUrl": "https://images.pexels.com/photos/1762851/pexels-photo-1762851.jpeg?auto=compress&cs=tinysrgb&w=800"},
  {"id": "bg2", "name": "Concrete", "thumbnailUrl": "https://images.pexels.com/photos/1191710/pexels-photo-1191710.jpeg?auto=compress&cs=tinysrgb&w=200", "fullUrl": "https://images.pexels.com/photos/1191710/pexels-photo-1191710.jpeg?auto=compress&cs=tinysrgb&w=800"},
  {"id": "bg3", "name": "Wood", "thumbnailUrl": "https://images.pexels.com/photos/129731/pexels-photo-129731.jpeg?auto=compress&cs=tinysrgb&w=200", "fullUrl": "https://images.pexels.com/photos/129731/pexels-photo-129731.jpeg?auto=compress&cs=tinysrgb&w=800"},
  {"id": "bg4", "name": "Marble", "thumbnailUrl": "https://images.pexels.com/photos/1139541/pexels-photo-1139541.jpeg?auto=compress&cs=tinysrgb&w=200", "fullUrl": "https://images.pexels.com/photos/1139541/pexels-photo-1139541.jpeg?auto=compress&cs=tinysrgb&w=800"},
]

@router.get("/", response_model=List[BackgroundResponse])
async def get_backgrounds():
    logger.info("Arka plan listesi isteği alındı.")
    return STATIC_BACKGROUNDS