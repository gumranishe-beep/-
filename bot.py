"""
Telegram Bot Handler для ShibaVPN
Запускай отдельно или интегрируй с бэкендом
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import WebAppInfo, MenuButtonWebApp
from aiogram.enums import ParseMode

from app.core.config import settings

logging.basicConfig(level=logging.INFO)

bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

WEBAPP_URL = "https://yourdomain.com"  # Заменить на реальный URL


@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    """Обработка /start и реферальных ссылок"""
    args = message.text.split()[1] if len(message.text.split()) > 1 else None

    # Обработка реферального кода
    if args and args.startswith("ref_"):
        referrer_id = int(args.split("_")[1])
        # Сохранить в БД (через API или напрямую)
        await process_referral(message.from_user.id, referrer_id)

    # Отправка приветствия с кнопкой Web App
    await message.answer(
        f"🐕 *Привет, {message.from_user.first_name}!*

"
        f"Я — Шиба, амбассадор бесплатного VPN!

"
        f"🛡️ *Бесплатный VPN* — до 3 устройств
"
        f"🍖 *Корми меня* — получай бонусы
"
        f"👥 *Приглашай друзей* — расширяй лимиты

"
        f"Нажми кнопку ниже, чтобы открыть приложение! 👇",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="🚀 Открыть ShibaVPN",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )],
                [types.InlineKeyboardButton(
                    text="📢 Наш канал",
                    url="https://t.me/ShibaVPNNews"
                )]
            ]
        )
    )


@dp.message(Command("vpn"))
async def cmd_vpn(message: types.Message):
    """Быстрая команда для получения конфига"""
    await message.answer(
        "🛡️ *Твой VPN-конфиг*

"
        "Открой приложение для управления подключением:",
        parse_mode=ParseMode.MARKDOWN,
        reply_markup=types.InlineKeyboardMarkup(
            inline_keyboard=[
                [types.InlineKeyboardButton(
                    text="🚀 Открыть ShibaVPN",
                    web_app=WebAppInfo(url=WEBAPP_URL)
                )]
            ]
        )
    )


@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    """Помощь"""
    await message.answer(
        "🐕 *Помощь от Шибы*

"
        "*/start* — Главное меню
"
        "*/vpn* — Управление VPN
"
        "*/help* — Эта справка

"
        "❓ По вопросам: @ShibaVPNSupport",
        parse_mode=ParseMode.MARKDOWN
    )


async def process_referral(user_id: int, referrer_id: int):
    """Обработка реферального перехода"""
    # TODO: Интеграция с API бэкенда
    logging.info(f"Referral: {user_id} from {referrer_id}")


async def set_webapp_button():
    """Установка кнопки Web App в меню"""
    await bot.set_chat_menu_button(
        menu_button=MenuButtonWebApp(
            text="ShibaVPN",
            web_app=WebAppInfo(url=WEBAPP_URL)
        )
    )


async def main():
    await set_webapp_button()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
