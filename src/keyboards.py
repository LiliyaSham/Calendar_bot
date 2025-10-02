from aiogram.types import ReplyKeyboardMarkup, KeyboardButton

# --- Главное меню ---
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📅 Добавить событие"), KeyboardButton(text="📋 Посмотреть события")],
        [KeyboardButton(text="🗑️ Удалить событие"), KeyboardButton(text="✏️ Изменить событие")]
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

# --- Клавиатура выхода из режима добавления ---
exit_add_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="❌ Выйти из режима добавления события")]
    ],
    resize_keyboard=True,
    one_time_keyboard=False
)
