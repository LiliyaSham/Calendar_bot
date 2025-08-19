from dotenv import load_dotenv
load_dotenv()

import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from supabase import create_client
import asyncio

# --- Конфиг ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Диагностика
print(f"🔹 TELEGRAM_BOT_TOKEN: {TELEGRAM_BOT_TOKEN}")
print(f"🔹 SUPABASE_URL: {SUPABASE_URL}")
print(f"🔹 SUPABASE_SERVICE_ROLE_KEY present: {bool(SUPABASE_SERVICE_ROLE_KEY)}")

if not TELEGRAM_BOT_TOKEN:
    raise ValueError("TELEGRAM_BOT_TOKEN not set!")


# --- Инициализация ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- FSM: Определение шагов ---
class EventForm(StatesGroup):
    title = State()
    description = State()
    start_datetime = State()
    end_datetime = State()
    place = State()
    weekly = State()

# --- Хендлеры ---
@dp.message(Command("start"))
async def start(message: Message, state: FSMContext):
    await state.set_state(EventForm.title)
    await message.answer("Привет! Напиши название события.")

@dp.message(EventForm.title, F.text)
async def set_title(message: Message, state: FSMContext):
    await state.update_data(event_title=message.text)
    await state.set_state(EventForm.description)
    await message.answer("Опиши событие.")

@dp.message(EventForm.description, F.text)
async def set_description(message: Message, state: FSMContext):
    await state.update_data(event_description=message.text)
    await state.set_state(EventForm.start_datetime)
    await message.answer("Когда начинается? (формат: YYYY-MM-DD HH:MM)")

@dp.message(EventForm.start_datetime, F.text)
async def set_start_datetime(message: Message, state: FSMContext):
    # Можно добавить валидацию
    await state.update_data(start_datetime=message.text)
    await state.set_state(EventForm.end_datetime)
    await message.answer("Когда заканчивается? (формат: YYYY-MM-DD HH:MM)")

@dp.message(EventForm.end_datetime, F.text)
async def set_end_datetime(message: Message, state: FSMContext):
    await state.update_data(end_datetime=message.text)
    await state.set_state(EventForm.place)
    await message.answer("Где проходит?")

@dp.message(EventForm.place, F.text)
async def set_place(message: Message, state: FSMContext):
    await state.update_data(event_place=message.text)
    await state.set_state(EventForm.weekly)
    await message.answer("Повторяется еженедельно? (да/нет)")

@dp.message(EventForm.weekly, F.text)
async def set_weekly(message: Message, state: FSMContext):
    text = message.text.lower()
    is_weekly = text in ["да", "yes", "true", "д", "y"]

    # Собираем все данные
    data = await state.get_data()
    telegram_id = message.from_user.id

    # Получаем или создаём пользователя
    try:
        user_res = supabase_client.table("users") \
            .select("id") \
            .eq("telegram_id", str(telegram_id)) \
            .execute()

        if user_res.data:
            user_id = user_res.data[0]["id"]
        else:
            new_user = supabase_client.table("users") \
                .insert({"telegram_id": str(telegram_id)}) \
                .execute()
            user_id = new_user.data[0]["id"]

        # Сохраняем событие
        event_data = {
            "user_id": user_id,
            "event_title": data["event_title"],
            "event_description": data["event_description"],
            "start_datetime": data["start_datetime"],
            "end_datetime": data["end_datetime"],
            "event_place": data["event_place"],
            "event_weekly": is_weekly,
        }

        supabase_client.table("events").insert(event_data).execute()
        await message.answer("✅ Событие успешно добавлено!")

    except Exception as e:
        await message.answer("❌ Ошибка при сохранении события.")
        print(f"Ошибка: {e}")

    # Завершаем FSM
    await state.clear()



# --- Запуск бота ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())


