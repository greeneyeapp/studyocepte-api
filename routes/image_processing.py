import io
import numpy as np
from fastapi import APIRouter, File, UploadFile, HTTPException, status
from fastapi.responses import StreamingResponse
from rembg import remove, new_session
from PIL import Image
from skimage import morphology
from scipy.ndimage import binary_erosion, binary_dilation, gaussian_filter

from loguru import logger # loguru import edildi

router = APIRouter()

REMBG_SESSION = new_session("isnet-general-use")

def apply_mask_to_image(original_bytes: bytes, mask_image: Image.Image) -> bytes:
    input_image = Image.open(io.BytesIO(original_bytes))
    input_image.putalpha(mask_image.convert("L"))
    
    output_buffer = io.BytesIO()
    input_image.save(output_buffer, format="PNG")
    return output_buffer.getvalue()

@router.post("/remove-background/", response_class=StreamingResponse)
async def remove_background(file: UploadFile = File(...)):
    logger.info(f"Arka plan kaldırma isteği alındı. Dosya: {file.filename}")
    if not file.content_type.startswith("image/"):
        logger.warning(f"Arka plan kaldırma: Geçersiz dosya tipi: {file.content_type}")
        raise HTTPException(status_code=400, detail="Yüklenen dosya bir resim değil.")

    input_image_bytes = await file.read()

    try:
        logger.info("Adım 1: Çoklu Maske Üretimi Başladı...")
        body_mask_bytes = remove(
            input_image_bytes,
            session=REMBG_SESSION,
            only_mask=True,
            alpha_matting=False
        )
        body_mask = Image.open(io.BytesIO(body_mask_bytes)).convert("L")

        details_mask_bytes = remove(
            input_image_bytes,
            session=REMBG_SESSION,
            only_mask=True,
            alpha_matting=True,
            alpha_matting_foreground_threshold=200,
            alpha_matting_background_threshold=20,
            alpha_matting_erode_size=10
        )
        details_mask = Image.open(io.BytesIO(details_mask_bytes)).convert("L")
        logger.info("Adım 1: Tamamlandı.")

        logger.info("Adım 2: Maskeleri Birleştirme Başladı...")
        body_array = np.array(body_mask) > 127
        details_array = np.array(details_mask) > 127
        combined_array = np.logical_or(body_array, details_array)
        logger.info("Adım 2: Tamamlandı.")

        logger.info("Adım 3: Maske Temizleme Başladı...")
        cleaned_array = morphology.remove_small_objects(combined_array, min_size=250)
        filled_array = morphology.remove_small_holes(cleaned_array, area_threshold=150)
        smoothed_array = gaussian_filter(filled_array.astype(float), sigma=1)
        final_mask = Image.fromarray((smoothed_array * 255).astype(np.uint8))
        logger.info("Adım 3: Tamamlandı.")

        logger.info("Adım 4: Nihai Çıktıyı Oluşturma...")
        output_image_bytes = apply_mask_to_image(input_image_bytes, final_mask)
        logger.info("Arka plan kaldırma işlemi başarıyla tamamlandı.")
        
        return StreamingResponse(io.BytesIO(output_image_bytes), media_type="image/png")

    except Exception as e:
        logger.error(f"Resim işlenirken hata oluştu: {e}")
        raise HTTPException(status_code=500, detail=f"Resim işlenirken bir hata oluştu: {str(e)}")