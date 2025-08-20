import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message
from supabase import create_client
import asyncio
import httpx
from datetime import datetime

# --- Конфиг ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"

async def extract_event_data(text: str) -> dict:
    """
    Отправляет текст в DeepSeek и извлекает структурированные данные
    Возвращает словарь с event_title, event_description, start_datetime, end_datetime
    """
    today = datetime.now().strftime('%Y-%m-%d')
    prompt = f"""
    Извлеки из сообщения информацию о событии.
    Верни ТОЛЬКО JSON в строгом формате:
    {{
      "event_title": "строка, обязательна",
      "event_description": "строка или null",
      "start_datetime": "строка в формате YYYY-MM-DD HH:MM или null",
      "end_datetime": "строка в формате YYYY-MM-DD HH:MM или null",
      "event_place": "строка (адрес, кафе, Zoom и т.п.) или null"
    }}

    Если дата/время указаны неявно (например, 'завтра', 'в понедельник'), рассчитай относительно сегодня: {today}.
    Если время окончания не указано — оставь как null.
    Если место не указано — event_place = null.

    Сообщение:
    {text}
    """

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            import json
            parsed = json.loads(content)

            # Гарантируем, что все ключи есть
            result = {
                "event_title": parsed.get("event_title"),
                "event_description": parsed.get("event_description"),
                "start_datetime": parsed.get("start_datetime"),
                "end_datetime": parsed.get("end_datetime"),
                "event_place": parsed.get("event_place")  # Может быть None
            }

            return result

        except Exception as e:
            print(f"Ошибка при обращении к DeepSeek: {e}")
            return {
                "event_title": None,
                "event_description": None,
                "start_datetime": None,
                "end_datetime": None,
                "event_place": None
            }


# --- Инициализация ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

@dp.message(F.text)
async def handle_free_text(message: Message):
    if message.text.startswith("/"):
        return  # Игнорируем команды

    await message.reply("🔍 Обрабатываю событие...")

    # Извлекаем данные через DeepSeek
    extracted = await extract_event_data(message.text)

    # Проверяем, есть ли хотя бы название и дата начала
    if not extracted["event_title"]:
        await message.reply("❌ Не удалось распознать название события.")
        return

    if not extracted["start_datetime"]:
        await message.reply("❌ Не удалось распознать дату и время начала.")
        return

    # Получаем или создаём пользователя
    try:
        user_res = supabase_client.table("users") \
            .select("id") \
            .eq("telegram_id", str(message.from_user.id)) \
            .execute()

        if user_res.data:
            user_id = user_res.data[0]["id"]
        else:
            new_user = supabase_client.table("users") \
                .insert({"telegram_id": str(message.from_user.id)}) \
                .execute()
            user_id = new_user.data[0]["id"]

        # Подготавливаем событие
        event_data = {
            "user_id": user_id,
            "event_title": extracted["event_title"],
            "event_description": extracted["event_description"],
            "start_datetime": extracted["start_datetime"],
            "end_datetime": extracted["end_datetime"],
            "event_place": extracted["event_place"],
            "event_weekly": False
        }

        # Сохраняем
        supabase_client.table("events").insert(event_data).execute()
        await message.reply(f"✅ Событие добавлено:\n\n"
                       f"**{extracted['event_title']}**\n"
                       f"🕐 {extracted['start_datetime']}\n"
                       f"{'📍 ' + extracted['event_place'] if extracted['event_place'] else ''}\n"
                       f"{'📝 ' + extracted['event_description'] if extracted['event_description'] else ''}")

    except Exception as e:
        await message.reply("❌ Ошибка при сохранении в базу.")
        print(f"Ошибка: {e}")





# --- Запуск бота ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":

    asyncio.run(main())
