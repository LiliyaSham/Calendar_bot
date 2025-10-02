from aiogram.fsm.state import StatesGroup, State

# --- FSM Состояния ---
class EventForm(StatesGroup):
    waiting_for_event = State()
    waiting_for_period = State()
    waiting_for_delete = State()
    confirming_delete = State()
    waiting_for_edit = State()
    confirming_edit = State()
