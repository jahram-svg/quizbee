import os

from dotenv import load_dotenv


load_dotenv()


FUNDING_BOT_TOKEN = os.getenv(
    "FUNDING_BOT_TOKEN"
)

FUNDING_BOT_USERNAME = os.getenv(
    "FUNDING_BOT_USERNAME",
    "QuizBeeFundingBot"
).strip().lstrip("@")


ADMIN_BOT_TOKEN = os.getenv(
    "ADMIN_BOT_TOKEN"
)

ADMIN_TELEGRAM_IDS = os.getenv(
    "ADMIN_TELEGRAM_IDS",
    os.getenv(
        "ADMIN_TELEGRAM_ID",
        ""
    )
)


def get_admin_ids():

    return [
        item.strip()
        for item in ADMIN_TELEGRAM_IDS.split(",")
        if item.strip()
    ]


if not FUNDING_BOT_TOKEN:

    raise ValueError(
        "FUNDING_BOT_TOKEN is missing."
  )
