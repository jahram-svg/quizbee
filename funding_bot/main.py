import asyncio

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

from funding_bot.config import (
    FUNDING_BOT_TOKEN
)

from funding_bot.handlers.funding import (
    router
)


async def main():

    bot = Bot(
        token=FUNDING_BOT_TOKEN,
        default=DefaultBotProperties(
            parse_mode=ParseMode.HTML
        )
    )

    dp = Dispatcher()

    dp.include_router(
        router
    )

    print(
        "🐝 QuizBee Funding Bot Started"
    )

    await dp.start_polling(
        bot
    )


if __name__ == "__main__":

    asyncio.run(
        main()
  )
