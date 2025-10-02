import httpx
import json
from datetime import datetime
from config import DEEPSEEK_API_KEY, DEEPSEEK_URL

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
