import os
from dotenv import load_dotenv
import firebase_admin

from firebase_admin import credentials
from firebase_admin import firestore

load_dotenv()

def initialize_firebase():
    """
    Initialize Firebase Admin SDK using environment variables.

    We deliberately do NOT load a service-account JSON file from the
    repository because QuizBee's repository is public.
    """

    if firebase_admin._apps:
        return firestore.client()

    project_id = os.getenv("FIREBASE_PROJECT_ID")
    client_email = os.getenv("FIREBASE_CLIENT_EMAIL")
    private_key = os.getenv("FIREBASE_PRIVATE_KEY")

    if not project_id:
        raise RuntimeError("Missing FIREBASE_PROJECT_ID")

    if not client_email:
        raise RuntimeError("Missing FIREBASE_CLIENT_EMAIL")

    if not private_key:
        raise RuntimeError("Missing FIREBASE_PRIVATE_KEY")

    private_key = private_key.replace("\\n", "\n")

    credential = credentials.Certificate({
        "type": "service_account",
        "project_id": project_id,
        "private_key": private_key,
        "client_email": client_email,
        "token_uri": "https://oauth2.googleapis.com/token",
    })

    firebase_admin.initialize_app(
        credential,
        {
            "projectId": project_id
        }
    )

    return firestore.client()


db = initialize_firebase()
