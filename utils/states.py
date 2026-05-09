from aiogram.fsm.state import State, StatesGroup


class ExchangeState(StatesGroup):
    """FSM states for the exchange flow."""
    select_from = State()      # User selecting FROM currency
    select_to = State()        # User selecting TO currency
    enter_amount = State()     # User entering amount
    enter_address = State()    # User entering destination address
    confirm = State()          # User confirming the exchange


class SkinState(StatesGroup):
    """FSM states for CS2 skin purchase flow."""
    search = State()           # User is typing a search query
    browse_results = State()   # User is browsing search results
    view_item = State()        # User is viewing a specific item
    select_crypto = State()    # User is selecting payment crypto
    enter_trade_url = State()  # User is entering Steam trade URL
    confirm = State()          # User is confirming the purchase


class AlertState(StatesGroup):
    """FSM states for the price alert flow."""
    select_currency = State()   # User selecting currency for alert
    select_direction = State()  # User selecting above/below
    enter_price = State()       # User entering target price


class PromoState(StatesGroup):
    """FSM states for the promo code flow."""
    enter_code = State()       # User is entering a promo code


class SupportState(StatesGroup):
    """FSM states for the support chat flow."""
    waiting_message = State()  # User is typing their support message


class BuyCryptoState(StatesGroup):
    """FSM states for the buy crypto with card flow."""
    select_crypto = State()    # User selecting which crypto to buy
    enter_amount = State()     # User entering USD amount
    enter_address = State()    # User entering wallet address