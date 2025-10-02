from aiogram import F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from datetime import datetime

from config import supabase_client
from keyboards import main_menu, confirm_kb, exit_add_kb
from states import EventForm
from utils import extract_event_data, extract_date_range, extract_event_to_delete, extract_edit_data


def clean_null_values(data):
    """Преобразует строки 'null' в Python None"""
    cleaned = {}
    for key, value in data.items():
        if value == "null" or value == "" or value is None:
            cleaned[key] = None
        else:
            cleaned[key] = value
    return cleaned


# --- Хендлер: старт и главное меню ---
async def cmd_start(message: Message):
    # Убираем любую предыдущую клавиатуру
    await message.answer(
        "👋 Привет! Я твой умный помощник по управлению расписанием через Telegram!\n\n"

        "📌 Я помогу тебе легко управлять событиями в календаре — просто напиши мне, что нужно добавить в календарь (или изменить, удалить, показать) в свободной форме,"
        "как будто говоришь с человеком.\n\n"

        "✨ <b>Что я умею:</b>\n"
        "• 📅 <b>Добавлять события в календарь</b> — напиши что-то вроде:\n"
        "  <code>Завтра в 18:00 встреча с командой в Zoom</code>\n"
        "• 🗓️ <b>Показывать события из календаря</b> — спроси:\n"
        "  <code>Какие у меня дела на завтра?</code>\n"
        "• ✏️ <b>Редактировать события в календаре</b> — скажи:\n"
        "  <code>Перенеси встречу на 19:00</code>\n"
        "• 🗑️ <b>Удалять события из календаря</b> — просто напиши:\n"
        "  <code>Удали презентацию в пятницу</code>\n\n"

        "🎯 Чтобы начать, выбери действие ниже:",
        parse_mode="HTML",
        reply_markup=main_menu
    )


# --- Хендлер: "Добавить событие" ---
async def add_event_handler(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_event)
    await message.answer("Напиши, какое событие нужно добавить, а также дату и время начала (если хочешь можешь добавть другую информацию):", reply_markup=None)


# --- Хендлер: "Посмотреть события" ---
async def view_events_handler(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_period)
    await message.answer("На какую дату или за какой период показать события?", reply_markup=None)


# --- Хендлер: Выход из режима добавления события ---
async def exit_add_event_mode(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Выход из режима добавления события. Что дальше?", reply_markup=main_menu)


# --- Хендлер: Получение события для добавления ---
async def handle_new_event(message: Message, state: FSMContext):
    await message.reply("🔍 Обрабатываю событие...")

    # Получаем сохраненные данные из предыдущих сообщений
    state_data = await state.get_data()
    saved_event = state_data.get("partial_event", {})

    # Извлекаем данные из текущего сообщения
    extracted = await extract_event_data(message.text)
    
    # Очищаем null значения
    extracted = clean_null_values(extracted)
    saved_event = clean_null_values(saved_event)

    # Объединяем сохраненные данные с новыми (новые имеют приоритет)
    merged_event = {
        "event_title": extracted["event_title"] or saved_event.get("event_title"),
        "event_description": extracted["event_description"] or saved_event.get("event_description"),
        "start_datetime": extracted["start_datetime"] or saved_event.get("start_datetime"),
        "end_datetime": extracted["end_datetime"] or saved_event.get("end_datetime"),
        "event_place": extracted["event_place"] or saved_event.get("event_place")
    }

    # Проверяем, что у нас есть минимально необходимые данные
    missing_title = not merged_event["event_title"]
    missing_datetime = not merged_event["start_datetime"]

    if missing_title or missing_datetime:
        # Сохраняем частичные данные для следующего сообщения
        await state.update_data(partial_event=merged_event)
        
        # Формируем сообщение с уже собранными данными
        collected_info = ""
        has_collected_data = False
        
        if merged_event["event_title"]:
            collected_info += f"• Название: <b>{merged_event['event_title']}</b>\n"
            has_collected_data = True
        if merged_event["start_datetime"]:
            collected_info += f"• Дата/время: <b>{merged_event['start_datetime']}</b>\n"
            has_collected_data = True
        if merged_event["event_place"]:
            collected_info += f"• Место: <b>{merged_event['event_place']}</b>\n"
            has_collected_data = True
        if merged_event["event_description"]:
            collected_info += f"• Описание: <b>{merged_event['event_description']}</b>\n"
            has_collected_data = True
        
        if has_collected_data:
            collected_info = "📝 Уже собрано:\n" + collected_info
        
        if missing_title and missing_datetime:
            error_msg = "❌ Не удалось распознать название события и дату/время начала.\n\n"
            if has_collected_data:
                error_msg += collected_info + "\n"
            error_msg += "🔍 Введите название события и дату/время или выйдите из режима добавления."
        elif missing_title:
            error_msg = "❌ Не удалось распознать название события.\n\n"
            if has_collected_data:
                error_msg += collected_info + "\n"
            error_msg += "🔍 Введите название события или выйдите из режима добавления."
        elif missing_datetime:
            error_msg = "❌ Не удалось распознать дату и время начала.\n\n"
            if has_collected_data:
                error_msg += collected_info + "\n"
            error_msg += "🔍 Введите дату и время или выйдите из режима добавления."
        
        await message.reply(error_msg, parse_mode="HTML", reply_markup=exit_add_kb)
        return

    # Если все данные есть, показываем что получилось и сохраняем
    extracted = clean_null_values(merged_event)

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
            f"✅ Событие добавлено в календарь:\n\n"
            f"<b>{extracted['event_title']}</b>\n"
            f"🕐 {extracted['start_datetime']}\n"
            f"{'📍 ' + extracted['event_place'] if extracted['event_place'] else ''}\n"
            f"{'📝 ' + extracted['event_description'] if extracted['event_description'] else ''}",
            parse_mode="HTML"
        )

    except Exception as e:
        # Сохраняем данные для повторной попытки
        await state.update_data(partial_event=extracted)
        await message.reply("❌ Ошибка при сохранении в базу.\n\nПопробуйте еще раз или выйдите из режима добавления.", reply_markup=exit_add_kb)
        print(f"Ошибка: {e}")
        return

    await state.clear()
    await message.answer("Что дальше?", reply_markup=main_menu)


# --- Хендлер: Получение периода для просмотра событий ---
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

        if not events_res.data or len(events_res.data) == 0:
            # Формируем сообщение с учетом времени
            if range_data["exact_time"]:
                await message.reply(f"На {start_date} в {range_data['exact_time']} нет запланированных событий.")
            else:
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
async def delete_event_handler(message: Message, state: FSMContext):
    await state.set_state(EventForm.waiting_for_delete)
    await message.answer(
        "Какое событие нужно удалить?\n"
        "Напиши название или упомяни дату.",
        reply_markup=None
    )


# --- Хендлер: Обработка запроса на удаление ---
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
        await message.answer("Что дальше?", reply_markup=main_menu)
        return

    else:
        await message.reply("Пожалуйста, выберите: ✅ Да или ❌ Нет")

