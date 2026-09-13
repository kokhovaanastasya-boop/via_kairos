# -*- coding: utf-8 -*-
"""
Бот «Кайрос» v2 — приветствие, проверка подписки, выдача подарка и сценарии.

СЦЕНАРИИ:
  1. /start             -> приветствие -> проверка подписки -> гайд или просьба подписаться
  2. Кнопка «Проверить» -> повторная проверка -> гайд
  3. После гайда        -> меню: Что внутри клуба / Тарифы / FAQ
  4. Текст «клуб»       -> инфо о клубе
  5. Текст «тариф/цена» -> тарифы и ссылка на оплату
  6. Текст «гайд»       -> заново выдать гайд (повторный заход по подписке)
  7. /help              -> подсказка
  8. /admin             -> простая статистика (если задан ADMIN_ID)
"""
import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    CallbackQuery,
    FSInputFile,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
)

# ====================== НАСТРОЙКИ (через переменные окружения) ======================
BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
CHANNEL_ID = os.getenv("CHANNEL_ID", "@kairos_club")     # канал, подписку на который проверяем
GIFT_PATH = os.getenv("GIFT_PATH", "guide.pdf")          # файл-подарок в корне репозитория
CLUB_URL = os.getenv("CLUB_URL", "https://boosty.to/kairos")  # ссылка на оплату/клуб
ADMIN_ID = os.getenv("ADMIN_ID", "").strip()             # твой Telegram id (для /admin)

# ================================ ТЕКСТЫ ============================================
WELCOME_TEXT = (
    "Привет, {name}! 👋\n"
    "Я — бот клуба «Кайрос».\n\n"
    "Чтобы забрать подарок — гайд «30 фраз, которые заменяют скандал»:\n\n"
    "1️⃣ Подпишись на канал {channel}\n"
    "2️⃣ Нажми кнопку ниже\n\n"
    "Это 30 секунд — зато сэкономишь пару скандалов в этом месяце 😄"
)

ALREADY_SUBSCRIBED_TEXT = "Привет, {name}! 👋 Ты уже в канале — держи подарок 🎁"

GIFT_CAPTION = "«30 фраз, которые заменяют скандал» 🎁"

GIFT_MISSING_TEXT = "Файл с подарком пока не загружен. Напиши админу 🙂"

PITCH_TEXT = (
    "Гайд у тебя 🎁\n\n"
    "А если хочешь глубже — есть закрытый клуб «Кайрос»: каждый день 🧠 инсайт, "
    "💰 приём про деньги, 🔥 задание на действие + разборы подписчиков.\n\n"
    "Смотри, что внутри 👇"
)

CLUB_TEXT = (
    "Клуб «Кайрос» — это закрытый Telegram-канал:\n\n"
    "• каждый день: 🧠 инсайт + 💰 приём про деньги + 🔥 задание на действие\n"
    "• раз в неделю: 🎙 аудио-разбор вопроса подписчицы\n"
    "• раз в месяц: 📕 воркбук (PDF)\n"
    "• закрытый чат без скандалов 🙂\n\n"
    "Готов(а) зайти? 👇"
)

PRICING_TEXT = (
    "Тарифы клуба «Кайрос»:\n\n"
    "🧪 Пробный месяц — 490 ₽\n"
    "💎 Месяц — 990 ₽\n"
    "👑 Квартал — 2490 ₽ (830 ₽/мес) + личный разбор\n\n"
    "Первым 20 участникам — 490 ₽ навсегда.\n\n"
    "Оплата: {club_url}"
)

FAQ_TEXT = (
    "Частые вопросы:\n\n"
    "❓ Гайд точно бесплатный?\n"
    "Да, полностью. Просто подписка на канал.\n\n"
    "❓ Когда выходят материалы?\n"
    "Каждый день: инсайт утром, деньги днём, мотивация вечером.\n\n"
    "❓ Можно ли отменить подписку?\n"
    "Да, в любой момент, без вопросов.\n\n"
    "❓ Есть ли возврат?\n"
    "Первая неделя — с гарантией возврата."
)

DEFAULT_TEXT = (
    "Я тебя не понял 😊\n\n"
    "Напиши:\n"
    "«клуб» — расскажу про клуб\n"
    "«тариф» — цены\n"
    "«гайд» — получить подарок"
)

HELP_TEXT = (
    "Команды:\n"
    "/start — начать заново\n"
    "/help — эта подсказка\n\n"
    "Или просто напиши: «клуб», «тариф», «гайд»"
)
# ====================================================================================


logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

stats = {"starts": 0, "gifts": 0}


# ----------------------------- клавиатуры ------------------------------------------
def check_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text="✅ Я подписался(ась) — забрать подарок",
            callback_data="check_sub",
        )]
    ])


def pitch_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🎁 Что внутри клуба", callback_data="club")],
        [InlineKeyboardButton(text="💳 Тарифы и оплата", callback_data="pricing")],
        [InlineKeyboardButton(text="❓ Частые вопросы", callback_data="faq")],
    ])


def back_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="↩️ Назад", callback_data="pitch")],
    ])


# ----------------------------- логика ------------------------------------------------
async def is_subscribed(user_id: int) -> bool:
    try:
        member = await bot.get_chat_member(chat_id=CHANNEL_ID, user_id=user_id)
        return member.status in ("member", "administrator", "creator")
    except Exception as e:
        logging.warning("Ошибка проверки подписки: %s", e)
        return False


async def send_gift(target: Message):
    """Выдаёт файл-подарок, затем меню с оффером клуба."""
    try:
        gift = FSInputFile(GIFT_PATH)
        await target.answer_document(gift, caption=GIFT_CAPTION)
        stats["gifts"] += 1
    except FileNotFoundError:
        await target.answer(GIFT_MISSING_TEXT)
        return
    await target.answer(PITCH_TEXT, reply_markup=pitch_kb())


async def handle_start(message: Message):
    stats["starts"] += 1
    name = message.from_user.full_name
    if await is_subscribed(message.from_user.id):
        await message.answer(ALREADY_SUBSCRIBED_TEXT.format(name=name))
        await send_gift(message)
    else:
        await message.answer(
            WELCOME_TEXT.format(name=name, channel=CHANNEL_ID),
            reply_markup=check_kb(),
        )


# ----------------------------- обработчики -------------------------------------------
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await handle_start(message)


@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(HELP_TEXT)


@dp.message(Command("admin"))
async def cmd_admin(message: Message):
    if ADMIN_ID and str(message.from_user.id) == str(ADMIN_ID):
        await message.answer(
            f"📊 Статистика (с момента запуска):\n"
            f"Запусков /start: {stats['starts']}\n"
            f"Выданных подарков: {stats['gifts']}"
        )
    else:
        await message.answer("Команда недоступна.")


@dp.callback_query(F.data == "check_sub")
async def cb_check(call: CallbackQuery):
    if await is_subscribed(call.from_user.id):
        await call.answer("✅ Подписка подтверждена!")
        await call.message.answer("Спасибо за подписку! Держи подарок 🎁")
        await send_gift(call.message)
    else:
        await call.answer(
            "❌ Подписка не найдена. Подпишись на канал и нажми кнопку ещё раз.",
            show_alert=True,
        )


@dp.callback_query(F.data == "club")
async def cb_club(call: CallbackQuery):
    await call.answer()
    await _edit_or_send(call, CLUB_TEXT, back_kb())


@dp.callback_query(F.data == "pricing")
async def cb_pricing(call: CallbackQuery):
    await call.answer()
    await _edit_or_send(call, PRICING_TEXT.format(club_url=CLUB_URL), back_kb())


@dp.callback_query(F.data == "faq")
async def cb_faq(call: CallbackQuery):
    await call.answer()
    await _edit_or_send(call, FAQ_TEXT, back_kb())


@dp.callback_query(F.data == "pitch")
async def cb_pitch(call: CallbackQuery):
    await call.answer()
    await _edit_or_send(call, PITCH_TEXT, pitch_kb())


async def _edit_or_send(call: CallbackQuery, text: str, kb: InlineKeyboardMarkup):
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)


@dp.message(F.text)
async def text_router(message: Message):
    t = message.text.lower()
    if any(w in t for w in ("клуб", "подробнее", "внутри")):
        await message.answer(CLUB_TEXT, reply_markup=pitch_kb())
    elif any(w in t for w in ("тариф", "цен", "сколько стоит", "оплат", "деньги")):
        await message.answer(PRICING_TEXT.format(club_url=CLUB_URL), reply_markup=pitch_kb())
    elif any(w in t for w in ("гайд", "подарок", "скандал", "фраз", "забрать")):
        await handle_start(message)
    elif any(w in t for w in ("faq", "вопрос")):
        await message.answer(FAQ_TEXT, reply_markup=pitch_kb())
    else:
        await message.answer(DEFAULT_TEXT, reply_markup=check_kb())


async def main():
    if not BOT_TOKEN:
        raise SystemExit("❌ BOT_TOKEN не задан. Укажи его в переменных окружения.")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
