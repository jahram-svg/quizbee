import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from bot.config import BOT_TOKEN
from bot.handlers.start import router


async def main():
    bot = Bot(
        token=BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dp = Dispatcher()

    dp.include_router(router)

    print("🐝 QuizBee Bot Started")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
