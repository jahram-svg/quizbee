import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
WEBAPP_URL = os.getenv("WEBAPP_URL")

if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN is missing from .env")

if not WEBAPP_URL:
    raise ValueError("WEBAPP_URL is missing from .env")
