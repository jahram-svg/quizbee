import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    Message,
    WebAppInfo,
    CallbackQuery,
)
from dotenv import load_dotenv


# ---------------------------------------------------------
# LOAD ENVIRONMENT
# ---------------------------------------------------------

load_dotenv()


ADMIN_BOT_TOKEN = os.getenv("ADMIN_BOT_TOKEN", "")
ADMIN_TELEGRAM_ID = os.getenv("ADMIN_TELEGRAM_ID", "")


# ---------------------------------------------------------
# ADMIN MINI APP
# ---------------------------------------------------------

ADMIN_APP_URL = "https://jahram-svg.github.io/quizbee/admin/"


# ---------------------------------------------------------
# LOGGING
# ---------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)

logger = logging.getLogger("quizbee_admin")


# ---------------------------------------------------------
# VALIDATE CONFIGURATION
# ---------------------------------------------------------

if not ADMIN_BOT_TOKEN:
    raise RuntimeError(
        "ADMIN_BOT_TOKEN is missing. Add it to your Codespaces secrets."
    )

if not ADMIN_TELEGRAM_ID:
    raise RuntimeError(
        "ADMIN_TELEGRAM_ID is missing. Add it to your Codespaces secrets."
    )


# ---------------------------------------------------------
# BOT SETUP
# ---------------------------------------------------------

bot = Bot(token=ADMIN_BOT_TOKEN)
dp = Dispatcher()


# ---------------------------------------------------------
# ADMIN SECURITY
# ---------------------------------------------------------

def is_admin(user_id: int) -> bool:
    return str(user_id) == str(ADMIN_TELEGRAM_ID)


async def reject_if_not_admin(message: Message) -> bool:
    if message.from_user is None:
        return True

    if not is_admin(message.from_user.id):
        await message.answer(
            "⛔ <b>Unauthorized</b>\n\n"
            "This bot is restricted to the QuizBee administrator."
        )
        return True

    return False


# ---------------------------------------------------------
# ADMIN MENU
# ---------------------------------------------------------

def admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Dashboard",
                    web_app=WebAppInfo(
                        url=f"{ADMIN_APP_URL}?section=dashboard"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="🎮 Games",
                    web_app=WebAppInfo(
                        url=f"{ADMIN_APP_URL}?section=games"
                    ),
                ),
                InlineKeyboardButton(
                    text="🧩 Challenges",
                    web_app=WebAppInfo(
                        url=f"{ADMIN_APP_URL}?section=challenges"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="💰 Daily Earning",
                    web_app=WebAppInfo(
                        url=f"{ADMIN_APP_URL}?section=daily"
                    ),
                )
            ],
            [
                InlineKeyboardButton(
                    text="💳 Withdrawals",
                    web_app=WebAppInfo(
                        url=f"{ADMIN_APP_URL}?section=withdrawals"
                    ),
                ),
                InlineKeyboardButton(
                    text="🪙 Point Purchases",
                    web_app=WebAppInfo(
                        url=f"{ADMIN_APP_URL}?section=orders"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="👥 Users",
                    web_app=WebAppInfo(
                        url=f"{ADMIN_APP_URL}?section=users"
                    ),
                ),
                InlineKeyboardButton(
                    text="📜 Transactions",
                    web_app=WebAppInfo(
                        url=f"{ADMIN_APP_URL}?section=transactions"
                    ),
                ),
            ],
            [
                InlineKeyboardButton(
                    text="⚙️ Settings",
                    web_app=WebAppInfo(
                        url=f"{ADMIN_APP_URL}?section=settings"
                    ),
                )
            ],
        ]
    )


# ---------------------------------------------------------
# /START
# ---------------------------------------------------------

@dp.message(Command("start"))
async def start_handler(message: Message):
    if await reject_if_not_admin(message):
        return

    await message.answer(
        "🔐 <b>QuizBee Admin</b>\n\n"
        "Welcome to the QuizBee administration panel.\n\n"
        "Use the menu below to manage the platform.",
        reply_markup=admin_menu(),
    )


# ---------------------------------------------------------
# /ADMIN
# ---------------------------------------------------------

@dp.message(Command("admin"))
async def admin_handler(message: Message):
    if await reject_if_not_admin(message):
        return

    await message.answer(
        "🔐 <b>QuizBee Admin Panel</b>\n\n"
        "Select an administration section:",
        reply_markup=admin_menu(),
    )


# ---------------------------------------------------------
# /PANEL
# ---------------------------------------------------------

@dp.message(Command("panel"))
async def panel_handler(message: Message):
    if await reject_if_not_admin(message):
        return

    await message.answer(
        "🔐 <b>QuizBee Admin Panel</b>\n\n"
        "Tap a section below.",
        reply_markup=admin_menu(),
    )


# ---------------------------------------------------------
# CALLBACK FALLBACK
# ---------------------------------------------------------

@dp.callback_query()
async def callback_handler(callback: CallbackQuery):
    if callback.from_user is None:
        return

    if not is_admin(callback.from_user.id):
        await callback.answer(
            "⛔ Unauthorized",
            show_alert=True,
        )
        return

    await callback.answer()


# ---------------------------------------------------------
# UNKNOWN MESSAGE
# ---------------------------------------------------------

@dp.message()
async def unknown_message_handler(message: Message):
    if await reject_if_not_admin(message):
        return

    await message.answer(
        "Use /start or /admin to open the QuizBee Admin Panel.",
        reply_markup=admin_menu(),
    )


# ---------------------------------------------------------
# MAIN
# ---------------------------------------------------------

async def main():
    logger.info("Starting QuizBee Admin Bot...")

    me = await bot.get_me()

    logger.info(
        "Admin bot started: @%s",
        me.username,
    )

    logger.info(
        "Admin Telegram ID configured: %s",
        ADMIN_TELEGRAM_ID,
    )

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
