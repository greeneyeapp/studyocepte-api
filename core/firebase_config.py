# studyocepte-api/core/firebase_config.py
import os
import firebase_admin
from firebase_admin import credentials, firestore
from google.oauth2 import service_account # Yeni import

SERVICE_ACCOUNT_KEY_PATH = "serviceAccountKey.json"

# Firebase Admin SDK için kimlik bilgisi (eskisi gibi)
cred = credentials.Certificate(SERVICE_ACCOUNT_KEY_PATH)

# Google Cloud Client Libraries için kimlik bilgisi (yeni)
# Bu, google.cloud.storage.Client() tarafından beklenen türdür
google_cloud_credentials = service_account.Credentials.from_service_account_file(
    SERVICE_ACCOUNT_KEY_PATH
)

if not firebase_admin._apps:
    if not os.path.exists(SERVICE_ACCOUNT_KEY_PATH):
        raise FileNotFoundError(
            f"Firebase hizmet hesabı anahtarı bulunamadı: {SERVICE_ACCOUNT_KEY_PATH}. "
            "Lütfen Firebase konsoldan indirin ve buraya yerleştirin."
        )
    firebase_admin.initialize_app(cred) # Firebase Admin SDK'yı başlat

db = firestore.client()

# cred ve google_cloud_credentials objelerini dışa aktarıyoruz
# cred Firebase Admin SDK tarafından kullanılırken,
# google_cloud_credentials diğer google.cloud client'ları tarafından kullanılacak