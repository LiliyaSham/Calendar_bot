from dotenv import load_dotenv
load_dotenv()

import os
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from supabase import create_client
import asyncio
import httpx
from datetime import datetime
import json

# --- Конфиг ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
DEEPSEEK_URL = "https://api.deepseek.com/v1/chat/completions"  # исправлено: лишние пробелы удалены

# --- Клиент Supabase ---
supabase_client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- Бот и диспетчер ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- Клавиатура ---
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Добавить событие")],
        [KeyboardButton(text="📋 Посмотреть события")],
        [KeyboardButton(text="🗑️ Удалить событие")],
        [KeyboardButton(text="✏️ Изменить событие")]  # ← новая кнопка
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)

# --- Клавиатура подтверждения ---
confirm_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Да"), KeyboardButton(text="❌ Нет")]
    ],
    resize_keyboard=True,
    one_time_keyboard=True
)

# --- FSM Состояния ---
class EventForm(StatesGroup):
    waiting_for_event = State()
    waiting_for_period = State()
    waiting_for_delete = State()
    confirming_delete = State()
    waiting_for_edit = State()
    confirming_edit = State()

# --- Функция: извлечение данных о событии ---
async def extract_event_data(text: str) -> dict:
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
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            return {
                "event_title": parsed.get("event_title"),
                "event_description": parsed.get("event_description"),
                "start_datetime": parsed.get("start_datetime"),
                "end_datetime": parsed.get("end_datetime"),
                "event_place": parsed.get("event_place")
            }
        except Exception as e:
            print(f"Ошибка при обращении к DeepSeek: {e}")
            return {
                "event_title": None,
                "event_description": None,
                "start_datetime": None,
                "end_datetime": None,
                "event_place": None
            }


# --- Функция: извлечение периода (для запроса событий) ---
async def extract_date_range(text: str) -> dict:
    """
    Анализирует текст и возвращает:
    {
        "start_date": "YYYY-MM-DD",
        "end_date": "YYYY-MM-DD",
        "start_time": "HH:MM",   # опционально
        "end_time": "HH:MM",     # опционально
        "exact_time": "HH:MM"    # если указано одно время
    }
    """
    today = datetime.now().strftime('%Y-%m-%d')
    prompt = f"""
    Определи диапазон дат и/или времени из сообщения.
    Верни ТОЛЬКО JSON в формате:
    {{
      "start_date": "YYYY-MM-DD или null",
      "end_date": "YYYY-MM-DD или null",
      "start_time": "HH:MM или null",
      "end_time": "HH:MM или null",
      "exact_time": "HH:MM или null"
    }}
    Сегодня: {today}

    Примеры:
    - "на 14 сентября в 18:00" → start_date=14-09, exact_time=18:00
    - "после 18:00 сегодня" → start_date=today, start_time=18:00
    - "до 12:00 завтра" → end_date=tomorrow, end_time=12:00
    - "вечером в пятницу" → start_date=friday, start_time="18:00", end_time="22:00"

    Сообщение:
    {text}
    """

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            return {
                "start_date": parsed.get("start_date"),
                "end_date": parsed.get("end_date"),
                "start_time": parsed.get("start_time"),
                "end_time": parsed.get("end_time"),
                "exact_time": parsed.get("exact_time")
            }
        except Exception as e:
            print(f"Ошибка при извлечении диапазона: {e}")
            return {
                "start_date": None,
                "end_date": None,
                "start_time": None,
                "end_time": None,
                "exact_time": None
            }

# --- Функция: извлечение названий событий для удаления ---
async def extract_event_to_delete(text: str) -> dict:
    """
    Извлекает данные для поиска события на удаление.
    Возвращает:
    {
        "event_title": "название или null",
        "start_date": "YYYY-MM-DD",
        "exact_time": "HH:MM"
    }
    """
    today = datetime.now().strftime('%Y-%m-%d')
    prompt = f"""
    Определи, какое событие нужно удалить.
    Верни ТОЛЬКО JSON в формате:
    {{
      "event_title": "название события или null",
      "start_date": "YYYY-MM-DD",
      "exact_time": "HH:MM"
    }}
    Сегодня: {today}

    Примеры:
    - "удали событие завтра в 12:00" → start_date=завтра, exact_time="12:00", event_title=null
    - "встречу с командой в 18:00" → event_title="встреча с командой", exact_time="18:00"
    - "на 14 сентября в 10:30" → start_date="2025-09-14", exact_time="10:30"

    Сообщение:
    {text}
    """

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            return {
                "event_title": parsed.get("event_title"),
                "start_date": parsed.get("start_date"),
                "exact_time": parsed.get("exact_time")
            }
        except Exception as e:
            print(f"Ошибка при извлечении данных для удаления: {e}")
            return {"event_title": None, "start_date": None, "exact_time": None}

# --- Функция: извлечение данных для изменения ---
async def extract_edit_data(text: str) -> dict:
    """
    Извлекает данные для изменения события.
    Возвращает поля, которые нужно обновить.
    start_datetime должен быть в формате ISO: YYYY-MM-DDTHH:MM:SS
    """
    today = datetime.now().strftime('%Y-%m-%d')
    prompt = f"""
    Определи, какие поля события нужно изменить.
    Верни ТОЛЬКО JSON с ПОЛЯМИ, КОТОРЫЕ МЕНЯЮТСЯ:
    {{
      "event_title": "новое название или null",
      "event_description": "новое описание или null",
      "start_datetime": "новая дата-время в формате YYYY-MM-DDTHH:MM:SS или null",
      "end_datetime": "новое окончание в формате YYYY-MM-DDTHH:MM:SS или null",
      "event_place": "новое место или null"
    }}

    Если указано "перенести на завтра в 19:00", то:
    start_datetime = "2025-09-15T19:00:00"

    Сегодня: {today}

    Сообщение:
    {text}
    """

    headers = {
        "Authorization": f"Bearer {DEEPSEEK_API_KEY}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": "deepseek-chat",
        "messages": [{"role": "user", "content": prompt}],
        "response_format": {"type": "json_object"},
        "temperature": 0.1
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        try:
            response = await client.post(DEEPSEEK_URL, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

            content = data["choices"][0]["message"]["content"]
            parsed = json.loads(content)

            # Приводим к нужному формату
            def validate_dt(dt_str):
                if not dt_str or len(dt_str) < 16:
                    return None
                # Проверяем, что это YYYY-MM-DDTHH:MM:SS
                import re
                if re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$", dt_str):
                    return dt_str
                return None

            return {
                "event_title": parsed.get("event_title"),
                "event_description": parsed.get("event_description"),
                "start_datetime": validate_dt(parsed.get("start_datetime")),
                "end_datetime": validate_dt(parsed.get("end_datetime")),
                "event_place": parsed.get("event_place")
            }
        except Exception as e:
            print(f"Ошибка при извлечении данных для редактирования: {e}")
            return {
                "event_title": None,
                "event_description": None,
                "start_datetime": None,
                "end_datetime": None,
                "event_place": None
            }


# --- Хендлер: старт и главное меню ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    # Убираем любую предыдущую клавиатуру
    await message.answer(
        "👋 Привет! Я — <b>умный бот для управления событиями</b>.\n\n"
        "Выбери, что ты хочешь сделать:",
        parse_mode="HTML",
        reply_markup=main_menu  # твоя клавиатура с двумя кнопками
    )


# --- Хендлер: "Добавить событие" ---
@dp.message(F.text == "📅 Добавить событие")
async def add_event_handler(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_event)
    await message.answer("Напиши, какое событие нужно добавить:", reply_markup=None)


# --- Хендлер: "Посмотреть события" ---
@dp.message(F.text == "📋 Посмотреть события")
async def view_events_handler(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_period)
    await message.answer("На какую дату или за какой период показать события?", reply_markup=None)


# --- Хендлер: Получение события для добавления ---
@dp.message(EventForm.waiting_for_event, F.text)
async def handle_new_event(message: Message, state: FSMContext):
    await message.reply("🔍 Обрабатываю событие...")

    extracted = await extract_event_data(message.text)

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

        user_id = user_res.data[0]["id"] if user_res.data else None

        if not user_id:
            new_user = supabase_client.table("users") \
                .insert({"telegram_id": str(message.from_user.id)}) \
                .execute()
            user_id = new_user.data[0]["id"]

        # Сохраняем событие
        event_data = {
            "user_id": user_id,
            "event_title": extracted["event_title"],
            "event_description": extracted["event_description"],
            "start_datetime": extracted["start_datetime"],
            "end_datetime": extracted["end_datetime"],
            "event_place": extracted["event_place"],
            "event_weekly": False
        }

        supabase_client.table("events").insert(event_data).execute()

        await message.reply(
            f"✅ Событие добавлено:\n\n"
            f"<b>{extracted['event_title']}</b>\n"
            f"🕐 {extracted['start_datetime']}\n"
            f"{'📍 ' + extracted['event_place'] if extracted['event_place'] else ''}\n"
            f"{'📝 ' + extracted['event_description'] if extracted['event_description'] else ''}",
            parse_mode="HTML"
        )

    except Exception as e:
        await message.reply("❌ Ошибка при сохранении в базу.")
        print(f"Ошибка: {e}")

    await state.clear()
    await message.answer("Что дальше?", reply_markup=main_menu)


# --- Хендлер: Получение периода для просмотра событий ---
@dp.message(EventForm.waiting_for_period, F.text)
async def handle_view_events(message: Message, state: FSMContext):
    await message.reply("🔍 Определяю период и время...")

    range_data = await extract_date_range(message.text)

    if not range_data["start_date"] and not range_data["end_date"]:
        await message.reply("❌ Не удалось определить дату.")
        await state.clear()
        await message.answer("Что дальше?", reply_markup=main_menu)
        return

    # Установим дефолтные значения
    start_date = range_data["start_date"] or range_data["end_date"]
    end_date = range_data["end_date"] or range_data["start_date"]

    try:
        # Получаем пользователя
        user_res = supabase_client.table("users") \
            .select("id") \
            .eq("telegram_id", str(message.from_user.id)) \
            .execute()

        if not user_res:
            await message.reply("❌ Пользователь не найден.")
            return

        user_id = user_res.data[0]["id"]

        # Начинаем строить запрос
        query = supabase_client.table("events") \
            .select("*") \
            .eq("user_id", user_id) \
            .gte("start_datetime", f"{start_date}T00:00:00") \
            .lte("start_datetime", f"{end_date}T23:59:59")

        # Фильтр по времени
        if range_data["exact_time"]:
            # Только события в точное время
            query = query.eq("start_datetime", f"{start_date}T{range_data['exact_time']}:00")

        else:
            # Диапазон времени
            if range_data["start_time"]:
                time_str = f"{start_date}T{range_data['start_time']}:00"
                query = query.gte("start_datetime", time_str)

            if range_data["end_time"]:
                time_str = f"{end_date}T{range_data['end_time']}:00"
                query = query.lte("start_datetime", time_str)

        events_res = query.order("start_datetime").execute()

        if not events_res:
            await message.reply(f"На {start_date} нет запланированных событий.")
        else:
            # Формируем ответ с датой и временем
            response = f"📅 События "
            if range_data["exact_time"]:
                response += f"на {start_date} в {range_data['exact_time']}:\n\n"
            elif range_data["start_time"] and not range_data["end_time"]:
                response += f"после {range_data['start_time']} на {start_date}:\n\n"
            elif range_data["end_time"] and not range_data["start_time"]:
                response += f"до {range_data['end_time']} на {start_date}:\n\n"
            else:
                response += f"с {start_date} по {end_date}:\n\n"

            for ev in events_res.data:
                title = ev["event_title"]

                if ev["start_datetime"]:
                    dt = ev["start_datetime"]
                    date_part = dt.split("T")[0]
                    time_part = dt.split("T")[1][:5]
                    try:
                        from datetime import datetime as dt_module
                        parsed = dt_module.fromisoformat(date_part)
                        formatted_date = parsed.strftime("%d.%m.%Y")
                        datetime_display = f"{formatted_date} {time_part}"
                    except:
                        datetime_display = f"{date_part} {time_part}"
                else:
                    datetime_display = "??.??.???? ??:??"

                place = f"\n📍 {ev['event_place']}" if ev["event_place"] else ""
                desc = f"\n📝 {ev['event_description']}" if ev["event_description"] else ""

                response += (
                    f"• <b>{title}</b> — {datetime_display}{place}{desc}\n\n"
                )

            await message.reply(response.strip(), parse_mode="HTML")

    except Exception as e:
        await message.reply("❌ Ошибка при получении событий.")
        print(f"Ошибка: {e}")

    await state.clear()
    await message.answer("Что дальше?", reply_markup=main_menu)

# --- Хендлер: Удаление события ---
@dp.message(F.text == "🗑️ Удалить событие")
async def delete_event_handler(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_delete)
    await message.answer(
        "Какое событие нужно удалить?\n"
        "Напиши название или упомяни дату.",
        reply_markup=None
    )

# --- Хендлер: Обработка запроса на удаление ---
@dp.message(EventForm.waiting_for_delete, F.text)
async def handle_delete_event(message: Message, state: FSMContext):
    await message.reply("🔍 Ищу событие для удаления...")

    # Извлекаем данные
    deletion_data = await extract_event_to_delete(message.text)

    if not deletion_data["start_date"]:
        await message.reply("❌ Не удалось определить дату события.")
        await state.clear()
        await message.answer("Что дальше?", reply_markup=main_menu)
        return

    try:
        # Получаем пользователя
        user_res = supabase_client.table("users") \
            .select("id") \
            .eq("telegram_id", str(message.from_user.id)) \
            .execute()

        if not user_res:
            await message.reply("❌ Пользователь не найден.")
            return

        user_id = user_res.data[0]["id"]

        # Формируем запрос
        query = supabase_client.table("events") \
            .select("*") \
            .eq("user_id", user_id) \
            .gte("start_datetime", f"{deletion_data['start_date']}T00:00:00") \
            .lte("start_datetime", f"{deletion_data['start_date']}T23:59:59")

        # Если указано точное время — фильтруем по нему
        if deletion_data["exact_time"]:
            target_time = f"{deletion_data['start_date']}T{deletion_data['exact_time']}:00"
            query = query.eq("start_datetime", target_time)

        # Если есть название — добавляем поиск по нему
        if deletion_data["event_title"]:
            query = query.ilike("event_title", f"%{deletion_data['event_title']}%")

        events_res = query.execute()

        if not events_res:
            await message.reply(f"❌ Событие на {deletion_data['start_date']} не найдено.")
            await state.clear()
            await message.answer("Что дальше?", reply_markup=main_menu)
            return

        # Сохраняем ID событий
        found_events = events_res.data
        event_ids = [ev["id"] for ev in found_events]

        # Показываем найденное событие
        first_ev = found_events[0]
        title = first_ev["event_title"] or "Без названия"

        if first_ev["start_datetime"]:
            dt = first_ev["start_datetime"]
            date_part = dt.split("T")[0]
            time_part = dt.split("T")[1][:5]
            try:
                from datetime import datetime as dt_module
                parsed = dt_module.fromisoformat(date_part)
                formatted_date = parsed.strftime("%d.%m.%Y")
                datetime_str = f"{formatted_date} {time_part}"
            except:
                datetime_str = f"{date_part} {time_part}"
        else:
            datetime_str = "??.??.???? ??:??"

        place = f"\n📍 {first_ev['event_place']}" if first_ev['event_place'] else ""
        desc = f"\n📝 {first_ev['event_description']}" if first_ev['event_description'] else ""

        confirmation_msg = (
            f"Найдено событие:\n\n"
            f"• <b>{title}</b> — {datetime_str}{place}{desc}\n\n"
            f"Вы уверены, что хотите его удалить?"
        )
        await message.reply(confirmation_msg, parse_mode="HTML", reply_markup=confirm_kb)

        # Сохраняем ID в состояние
        await state.update_data(event_ids_to_delete=event_ids)
        await state.set_state(EventForm.confirming_delete)

    except Exception as e:
        await message.reply("❌ Ошибка при поиске события.")
        print(f"Ошибка: {e}")
        await state.clear()
        await message.answer("Что дальше?", reply_markup=main_menu)

# --- Хендлер: Подтверждение удаления ---
@dp.message(EventForm.confirming_delete, F.text)
async def confirm_delete(message: Message, state: FSMContext):
    if message.text == "❌ Нет":
        await message.reply("❌ Удаление отменено.", reply_markup=main_menu)
        await state.clear()
        return

    elif message.text == "✅ Да":
        data = await state.get_data()
        event_ids = data.get("event_ids_to_delete", [])

        try:
            # Удаляем события
            supabase_client.table("events").delete().in_("id", event_ids).execute()
            count = len(event_ids)
            s = "событие" if count == 1 else "события"
            await message.reply(f"✅ Успешно удалено {count} {s}.", reply_markup=main_menu)
        except Exception as e:
            await message.reply("❌ Ошибка при удалении события.")
            print(f"Ошибка: {e}")

        await state.clear()
        return

    else:
        await message.reply("Пожалуйста, выберите: ✅ Да или ❌ Нет")

# --- Хендлер: Изменение события ---
@dp.message(F.text == "✏️ Изменить событие")
async def edit_event_handler(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_edit)
    await message.answer(
        "Какое событие нужно изменить?\n"
        "Напиши, что нужно поменять.\n\n"
        "Примеры:\n"
        "• Перенеси встречу с командой на завтра в 19:00\n"
        "• Измени название презентации на 'Демо продукта'\n"
        "• Перенеси созвон в Zoom",
        reply_markup=None
    )

# --- Хендлер: Обработка запроса на изменение ---
@dp.message(EventForm.waiting_for_edit, F.text)
async def handle_edit_event(message: Message, state: FSMContext):
    await message.reply("🔍 Ищу событие для изменения...")

    # Шаг 1: Извлечь, ЧТО менять
    changes = await extract_edit_data(message.text)
    if not any(value is not None for value in changes.values()):
        await message.reply("❌ Не удалось определить, что нужно изменить.")
        await state.clear()
        await message.answer("Что дальше?", reply_markup=main_menu)
        return

    # Шаг 2: Найти событие по контексту (названию, дате и т.п.)
    # Для простоты используем ту же логику, что и при удалении
    deletion_like_data = await extract_event_to_delete(message.text)

    if not deletion_like_data["start_date"] and not changes.get("start_datetime"):
        await message.reply("❌ Не удалось определить, какое событие изменить.")
        await state.clear()
        await message.answer("Что дальше?", reply_markup=main_menu)
        return

    try:
        user_res = supabase_client.table("users") \
            .select("id") \
            .eq("telegram_id", str(message.from_user.id)) \
            .execute()

        if not user_res:
            await message.reply("❌ Пользователь не найден.")
            return

        user_id = user_res.data[0]["id"]

        # Поиск события
        query = supabase_client.table("events") \
            .select("*") \
            .eq("user_id", user_id)

        found_event = None

        # Приоритет: если есть точное время + дата — ищем по ним
        if deletion_like_data["start_date"] and deletion_like_data["exact_time"]:
            target_dt = f"{deletion_like_data['start_date']}T{deletion_like_data['exact_time']}:00"
            query = query.eq("start_datetime", target_dt)
            res = query.execute()
            if res:
                found_event = res.data[0]

        # Или по названию
        elif deletion_like_data["event_title"]:
            res = query.ilike("event_title", f"%{deletion_like_data['event_title']}%").execute()
            if res:
                found_event = res.data[0]

        # Или просто самое последнее
        else:
            res = query.order("start_datetime", desc=True).limit(1).execute()
            if res.data and len(res.data) > 0:
                found_event = res.data[0]
            else:
                found_event = None

        if not found_event:
            await message.reply("❌ Событие не найдено.")
            await state.clear()
            await message.answer("Что дальше?", reply_markup=main_menu)
            return

        # Применяем изменения
        updated_fields = {}
        old_values = {}

        for field in ["event_title", "event_description", "event_place"]:
            new_val = changes.get(field)
            if new_val:
                old_values[field] = found_event[field]
                updated_fields[field] = new_val

        # Обновление времени
        if changes["start_datetime"]:
            old_values["start_datetime"] = found_event["start_datetime"]
            updated_fields["start_datetime"] = changes["start_datetime"]

        if changes["end_datetime"]:
            old_values["end_datetime"] = found_event["end_datetime"]
            updated_fields["end_datetime"] = changes["end_datetime"]

        if not updated_fields:
            await message.reply("❌ Нечего изменять.")
            await state.clear()
            await message.answer("Что дальше?", reply_markup=main_menu)
            return

        # Показываем старые и новые значения
        details = ""
        for key, new_val in updated_fields.items():
            old_val = old_values.get(key, "не задано")
            if key == "start_datetime":
                old_val = old_val.split("T")[1][:5] if old_val else "??:??"
                new_val_time = new_val.split("T")[1][:5] if "T" in new_val else new_val
                details += f"🕐 Время: {old_val} → {new_val_time}\n"
            elif key == "event_title":
                details += f"📌 Название: {old_val} → {new_val}\n"
            elif key == "event_place":
                details += f"📍 Место: {old_val or 'не задано'} → {new_val}\n"
            elif key == "event_description":
                details += f"📝 Описание: {old_val or 'не задано'} → {new_val}\n"

        confirmation_msg = (
            f"Будет изменено:\n\n"
            f"Старые данные:\n"
            f"• <b>{found_event['event_title']}</b>"
            f" — {found_event['start_datetime'].split('T')[1][:5] if found_event['start_datetime'] else '??:??'}\n\n"
            f"Новые значения:\n"
            f"{details}\n"
            f"Подтвердите изменение:"
        )

        await message.reply(confirmation_msg, parse_mode="HTML", reply_markup=confirm_kb)
        await state.update_data(event_id=found_event["id"], updated_fields=updated_fields)
        await state.set_state(EventForm.confirming_edit)

    except Exception as e:
        await message.reply("❌ Ошибка при поиске события.")
        print(f"Ошибка: {e}")
        await state.clear()
        await message.answer("Что дальше?", reply_markup=main_menu)

# --- Хендлер: Подтверждение редактирования ---
@dp.message(EventForm.confirming_edit, F.text)
async def confirm_edit(message: Message, state: FSMContext):
    if message.text == "❌ Нет":
        await message.reply("❌ Изменение отменено.", reply_markup=main_menu)
        await state.clear()
        return

    elif message.text == "✅ Да":
        data = await state.get_data()
        event_id = data.get("event_id")
        updated_fields = data.get("updated_fields", {})

        try:
            supabase_client.table("events").update(updated_fields).eq("id", event_id).execute()
            await message.reply("✅ Событие успешно изменено!", reply_markup=main_menu)
        except Exception as e:
            await message.reply("❌ Ошибка при сохранении изменений.")
            print(f"Ошибка: {e}")

        await state.clear()
        return

    else:
        await message.reply("Пожалуйста, выберите: ✅ Да или ❌ Нет")


# --- Запуск бота ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())


