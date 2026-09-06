from aiogram import Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

from bot.config import WEBAPP_URL

router = Router()


@router.message(CommandStart())
async def start_handler(message: Message):

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="🐝 Open QuizBee",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )
            ]
        ]
    )

    await message.answer(
        f"""
<b>🐝 Welcome to QuizBee!</b>

Play. Compete. Win. 🏆

Test your brain across different challenges:

🎯 Guess It
🕵️ Who Am I?
💀 Impossible Question

More games coming soon.

Ready to play?
""",
        reply_markup=keyboard
    )
