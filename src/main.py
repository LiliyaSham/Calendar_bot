from dotenv import load_dotenv
load_dotenv()

import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.storage.memory import MemoryStorage

from config import TELEGRAM_BOT_TOKEN
from states import EventForm
from handlers import (
    cmd_start, add_event_handler, view_events_handler, exit_add_event_mode,
    handle_new_event, handle_view_events, delete_event_handler, handle_delete_event,
    confirm_delete, edit_event_handler, handle_edit_event, confirm_edit
)

# --- Бот и диспетчер ---
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- Регистрация хендлеров ---
# Команда старт
dp.message.register(cmd_start, Command("start"))

# Основные кнопки меню
dp.message.register(add_event_handler, F.text == "📅 Добавить событие")
dp.message.register(view_events_handler, F.text == "📋 Посмотреть события")
dp.message.register(delete_event_handler, F.text == "🗑️ Удалить событие")
dp.message.register(edit_event_handler, F.text == "✏️ Изменить событие")

# Обработчики состояний
dp.message.register(exit_add_event_mode, EventForm.waiting_for_event, F.text == "❌ Выйти из режима добавления события")
dp.message.register(handle_new_event, EventForm.waiting_for_event, F.text)
dp.message.register(handle_view_events, EventForm.waiting_for_period, F.text)
dp.message.register(handle_delete_event, EventForm.waiting_for_delete, F.text)
dp.message.register(confirm_delete, EventForm.confirming_delete, F.text)
dp.message.register(handle_edit_event, EventForm.waiting_for_edit, F.text)
dp.message.register(confirm_edit, EventForm.confirming_edit, F.text)

# --- Запуск бота ---
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
