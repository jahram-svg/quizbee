import firebase_admin
from firebase_admin import credentials, firestore
import os


db = None


def initialize_firebase():

    global db

    if db is not None:
        return db

    credentials_path = os.getenv(
        "FIREBASE_CREDENTIALS",
        "serviceAccountKey.json"
    )

    if not os.path.exists(credentials_path):
        print("⚠️ Firebase credentials not found.")
        print("Firebase will remain disabled for now.")
        return None

    cred = credentials.Certificate(credentials_path)

    if not firebase_admin._apps:
        firebase_admin.initialize_app(cred)

    db = firestore.client()

    print("🔥 Firebase connected")

    return db
