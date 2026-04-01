from aiogram.fsm.state import State, StatesGroup


class ExchangeState(StatesGroup):
    """FSM states for the exchange flow."""
    select_from = State()      # User selecting FROM currency
    select_to = State()        # User selecting TO currency
    enter_amount = State()     # User entering amount
    enter_address = State()    # User entering destination address
    confirm = State()          # User confirming the exchange