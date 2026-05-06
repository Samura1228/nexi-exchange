import logging
from decimal import Decimal

from aiogram import Router, types, F
from aiogram.fsm.context import FSMContext
from sqlalchemy import select

from config import SKINS_TEST_USER_IDS, SKINS_MARKUP_PERCENT, SUPPORTED_CURRENCIES
from database import async_session, User, SkinTransaction
from services.dmarket import dmarket
from services.price_service import get_crypto_price_usd, usd_to_crypto
from utils.states import SkinState
from keyboards.builders import (
    get_start_keyboard,
    get_skin_search_keyboard,
    get_skin_results_keyboard,
    get_skin_item_keyboard,
    get_skin_confirm_keyboard,
)
from sheets import log_action

logger = logging.getLogger(__name__)
router = Router()

ITEMS_PER_PAGE = 5


def _is_test_user(user_id: int) -> bool:
    """Check if user has access to skins feature."""
    return user_id in SKINS_TEST_USER_IDS


def _find_display_name(ticker: str, network: str) -> str:
    """Find display name for a currency from SUPPORTED_CURRENCIES."""
    for display, t, n in SUPPORTED_CURRENCIES:
        if t == ticker and n == network:
            return display
    return ticker.upper()


def _parse_dmarket_items(data: dict) -> list:
    """Parse DMarket search response into a simplified list of items."""
    objects = data.get("objects", [])
    items = []
    for obj in objects:
        try:
            # DMarket prices are in USD cents in the "price" field
            price_data = obj.get("price", {})
            price_cents = int(price_data.get("USD", "0"))
            price_usd = price_cents / 100.0

            title = obj.get("title", "Unknown Item")
            offer_id = obj.get("extra", {}).get("offerId", "") or obj.get("itemId", "")

            # Get exterior/wear info
            extra = obj.get("extra", {})
            exterior = extra.get("exterior", "")

            full_title = f"{title} ({exterior})" if exterior else title

            items.append({
                "offer_id": offer_id,
                "title": full_title,
                "price_usd": price_usd,
                "price_cents": price_cents,
                "image": obj.get("image", ""),
            })
        except (ValueError, KeyError, TypeError) as e:
            logger.warning(f"Failed to parse DMarket item: {e}")
            continue
    return items


@router.callback_query(F.data == "start_skins")
async def start_skins(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Entry point for CS2 skins purchase flow."""
    user_id = callback_query.from_user.id

    if not _is_test_user(user_id):
        await callback_query.answer("This feature is not available yet.", show_alert=True)
        return

    if not dmarket.is_configured():
        await callback_query.message.edit_text(
            "⚠️ CS2 Skins feature is not configured yet.\n"
            "DMarket API keys are missing.\n\n"
            "Please contact the admin.",
            reply_markup=get_start_keyboard(user_id),
        )
        await callback_query.answer()
        return

    await state.clear()
    await callback_query.message.edit_text(
        "🔫 **CS2 Skins Exchange**\n\n"
        "Search for any CS2 skin by name.\n"
        "Type your search query below:\n\n"
        "_Example: AK-47 Redline, Butterfly Knife, AWP Dragon Lore_",
        reply_markup=get_skin_search_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(SkinState.search)
    await callback_query.answer()


@router.message(SkinState.search)
async def process_search(message: types.Message, state: FSMContext) -> None:
    """Process skin search query."""
    user_id = message.from_user.id
    if not _is_test_user(user_id):
        return

    query = message.text.strip()
    if len(query) < 2:
        await message.answer(
            "❌ Search query too short. Please enter at least 2 characters.",
            reply_markup=get_skin_search_keyboard(),
        )
        return

    loading_msg = await message.answer(f"🔍 Searching for **{query}**...", parse_mode="Markdown")

    # Search DMarket
    result = await dmarket.search_items(title=query, limit=ITEMS_PER_PAGE, offset=0)

    if "error" in result:
        await loading_msg.edit_text(
            f"❌ Search failed: {result['error']}\n\nPlease try again.",
            reply_markup=get_skin_search_keyboard(),
        )
        return

    items = _parse_dmarket_items(result)
    total_items = result.get("total", {}).get("items", 0) if isinstance(result.get("total"), dict) else 0

    if not items:
        await loading_msg.edit_text(
            f"😕 No results found for **{query}**.\n\nTry a different search term.",
            reply_markup=get_skin_search_keyboard(),
            parse_mode="Markdown",
        )
        return

    # Save search state for pagination and back navigation
    await state.update_data(
        search_query=query,
        search_offset=0,
        search_total=total_items,
        search_items=[item for item in items],  # Store current page items
    )

    await loading_msg.edit_text(
        f"🔫 **CS2 Skins — Results for \"{query}\"**\n"
        f"Found {total_items} items. Select one to view details:\n",
        reply_markup=get_skin_results_keyboard(items, offset=0, total=total_items, limit=ITEMS_PER_PAGE),
        parse_mode="Markdown",
    )
    await state.set_state(SkinState.browse_results)


@router.callback_query(SkinState.browse_results, F.data.startswith("skin_page:"))
async def handle_pagination(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Handle pagination through search results."""
    user_id = callback_query.from_user.id
    if not _is_test_user(user_id):
        return

    offset = int(callback_query.data.split(":")[1])
    data = await state.get_data()
    query = data.get("search_query", "")

    # Fetch new page
    result = await dmarket.search_items(title=query, limit=ITEMS_PER_PAGE, offset=offset)

    if "error" in result:
        await callback_query.answer(f"Error: {result['error']}", show_alert=True)
        return

    items = _parse_dmarket_items(result)
    total_items = result.get("total", {}).get("items", 0) if isinstance(result.get("total"), dict) else 0

    await state.update_data(
        search_offset=offset,
        search_total=total_items,
        search_items=items,
    )

    await callback_query.message.edit_text(
        f"🔫 **CS2 Skins — Results for \"{query}\"**\n"
        f"Found {total_items} items (page {offset // ITEMS_PER_PAGE + 1}):\n",
        reply_markup=get_skin_results_keyboard(items, offset=offset, total=total_items, limit=ITEMS_PER_PAGE),
        parse_mode="Markdown",
    )
    await callback_query.answer()


@router.callback_query(SkinState.browse_results, F.data == "skin_new_search")
async def handle_new_search(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Restart skin search."""
    user_id = callback_query.from_user.id
    if not _is_test_user(user_id):
        return

    await callback_query.message.edit_text(
        "🔫 **CS2 Skins Exchange**\n\n"
        "Type your search query below:\n\n"
        "_Example: AK-47 Redline, Butterfly Knife, AWP Dragon Lore_",
        reply_markup=get_skin_search_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(SkinState.search)
    await callback_query.answer()


@router.callback_query(SkinState.browse_results, F.data.startswith("skin_view:"))
async def view_item(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """View details of a specific skin item."""
    user_id = callback_query.from_user.id
    if not _is_test_user(user_id):
        return

    offer_id = callback_query.data.split(":", 1)[1]
    data = await state.get_data()
    items = data.get("search_items", [])

    # Find the item in current results
    item = None
    for i in items:
        if i["offer_id"] == offer_id:
            item = i
            break

    if not item:
        await callback_query.answer("Item not found. Please search again.", show_alert=True)
        return

    price_usd = item["price_usd"]
    markup_price = price_usd * (1 + SKINS_MARKUP_PERCENT / 100)

    # Get crypto prices for display
    price_lines = []
    for display_name, ticker, network in SUPPORTED_CURRENCIES[:5]:  # Show top 5 cryptos
        crypto_price = await get_crypto_price_usd(ticker)
        if crypto_price:
            crypto_amount = usd_to_crypto(markup_price, crypto_price)
            price_lines.append(f"  💰 {crypto_amount:.8g} {display_name}")

    prices_text = "\n".join(price_lines) if price_lines else "  ⚠️ Price data unavailable"

    await state.update_data(
        selected_item=item,
        selected_offer_id=offer_id,
        markup_price_usd=markup_price,
    )

    await callback_query.message.edit_text(
        f"🔫 **{item['title']}**\n\n"
        f"💵 **Market Price:** ${price_usd:.2f}\n"
        f"💵 **Our Price:** ${markup_price:.2f}\n\n"
        f"**Pay with crypto:**\n{prices_text}\n\n"
        f"Select your payment method below:",
        reply_markup=get_skin_item_keyboard(offer_id),
        parse_mode="Markdown",
    )
    await state.set_state(SkinState.view_item)
    await callback_query.answer()


@router.callback_query(SkinState.view_item, F.data.startswith("skin_pay:"))
async def select_payment(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """User selected a crypto to pay with. Ask for Steam trade URL."""
    user_id = callback_query.from_user.id
    if not _is_test_user(user_id):
        return

    # Parse: skin_pay:{offer_id}:{ticker}:{network}
    parts = callback_query.data.split(":")
    offer_id = parts[1]
    ticker = parts[2]
    network = parts[3]
    display_name = _find_display_name(ticker, network)

    data = await state.get_data()
    markup_price_usd = data.get("markup_price_usd", 0)

    # Get crypto price
    crypto_price = await get_crypto_price_usd(ticker)
    if not crypto_price:
        await callback_query.answer("Could not get crypto price. Try again.", show_alert=True)
        return

    crypto_amount = usd_to_crypto(markup_price_usd, crypto_price)

    await state.update_data(
        pay_ticker=ticker,
        pay_network=network,
        pay_display=display_name,
        pay_crypto_amount=crypto_amount,
        pay_crypto_price_usd=crypto_price,
    )

    item = data.get("selected_item", {})

    await callback_query.message.edit_text(
        f"🔫 **{item.get('title', 'CS2 Skin')}**\n"
        f"💰 **Price:** {crypto_amount:.8g} {display_name} (~${markup_price_usd:.2f})\n\n"
        f"🎮 **Enter your Steam Trade URL:**\n\n"
        f"_You can find it at:_\n"
        f"Steam → Inventory → Trade Offers → Who can send me Trade Offers?\n"
        f"Or visit: https://steamcommunity.com/my/tradeoffers/privacy\n\n"
        f"_Paste your trade URL below:_",
        reply_markup=get_skin_search_keyboard(),  # Just cancel button
        parse_mode="Markdown",
    )
    await state.set_state(SkinState.enter_trade_url)
    await callback_query.answer()


@router.message(SkinState.enter_trade_url)
async def process_trade_url(message: types.Message, state: FSMContext) -> None:
    """Process Steam trade URL and show confirmation."""
    user_id = message.from_user.id
    if not _is_test_user(user_id):
        return

    trade_url = message.text.strip()

    # Basic validation
    if "steamcommunity.com/tradeoffer" not in trade_url.lower():
        await message.answer(
            "❌ That doesn't look like a valid Steam Trade URL.\n\n"
            "It should look like:\n"
            "`https://steamcommunity.com/tradeoffer/new/?partner=XXXXX&token=XXXXX`\n\n"
            "Please try again.",
            reply_markup=get_skin_search_keyboard(),
            parse_mode="Markdown",
        )
        return

    await state.update_data(steam_trade_url=trade_url)
    data = await state.get_data()

    item = data.get("selected_item", {})
    pay_display = data.get("pay_display", "")
    crypto_amount = data.get("pay_crypto_amount", 0)
    markup_price_usd = data.get("markup_price_usd", 0)

    await message.answer(
        f"📋 **Purchase Confirmation:**\n\n"
        f"🔫 **Skin:** {item.get('title', 'CS2 Skin')}\n"
        f"💰 **Price:** {crypto_amount:.8g} {pay_display} (~${markup_price_usd:.2f})\n"
        f"🎮 **Steam Trade URL:** `{trade_url[:50]}...`\n\n"
        f"⚠️ After confirming, you will receive a deposit address.\n"
        f"Send the exact crypto amount to complete the purchase.\n\n"
        f"Press **Confirm** to proceed or **Cancel** to abort.",
        reply_markup=get_skin_confirm_keyboard(),
        parse_mode="Markdown",
    )
    await state.set_state(SkinState.confirm)


@router.callback_query(SkinState.confirm, F.data == "skin_confirm")
async def confirm_purchase(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """
    Confirm the skin purchase.

    MVP approach: Create a ChangeNow exchange to convert user's crypto to USDT (TRC20),
    which the admin will use to manually fund DMarket and send the skin.
    Save the SkinTransaction for tracking.
    """
    user_id = callback_query.from_user.id
    username = callback_query.from_user.username

    if not _is_test_user(user_id):
        return

    data = await state.get_data()
    item = data.get("selected_item", {})
    offer_id = data.get("selected_offer_id", "")
    markup_price_usd = data.get("markup_price_usd", 0)
    pay_ticker = data.get("pay_ticker", "")
    pay_network = data.get("pay_network", "")
    pay_display = data.get("pay_display", "")
    crypto_amount = data.get("pay_crypto_amount", 0)
    steam_trade_url = data.get("steam_trade_url", "")

    await callback_query.message.edit_text("⏳ Creating your skin purchase order...")

    # For MVP: Create a ChangeNow exchange from user's crypto to USDT (TRC20)
    # The admin will manually process the DMarket purchase
    from services.changenow import changenow

    # If user is already paying with USDT, we just need a deposit address
    # Otherwise, convert to USDT TRC20
    if pay_ticker == "usdt":
        # User pays USDT directly — for MVP just save the order and show instructions
        deposit_msg = await callback_query.message.edit_text(
            f"✅ **Skin Purchase Order Created!**\n\n"
            f"🔫 **Skin:** {item.get('title', 'CS2 Skin')}\n"
            f"💰 **Amount:** {crypto_amount:.8g} {pay_display}\n"
            f"🎮 **Steam Trade URL:** Saved\n\n"
            f"📬 **Payment:** Please contact admin to complete this purchase.\n"
            f"🔄 **Status:** ⏳ Awaiting payment\n\n"
            f"_The admin will process your order and send a Steam trade offer._",
            parse_mode="Markdown",
        )
        changenow_id = None
        deposit_address = "manual"
    else:
        # Create ChangeNow exchange: user's crypto → USDT TRC20
        result = await changenow.create_exchange(
            from_currency=pay_ticker,
            from_network=pay_network,
            to_currency="usdt",
            to_network="trx",
            amount=crypto_amount,
            address="TBD",  # Admin's USDT address — will need to be configured
        )

        if "error" in result:
            await callback_query.message.edit_text(
                f"❌ Failed to create payment.\n\nError: {result['error']}\n\nPlease try again.",
                reply_markup=get_start_keyboard(user_id),
            )
            await state.clear()
            await callback_query.answer()
            return

        changenow_id = result.get("id")
        deposit_address = result.get("payinAddress", "")
        payin_extra_id = result.get("payinExtraId", "")

        extra_id_text = f"\n🏷️ **Memo/Tag:** `{payin_extra_id}`" if payin_extra_id else ""

        deposit_msg = await callback_query.message.edit_text(
            f"✅ **Skin Purchase Order Created!**\n\n"
            f"🔫 **Skin:** {item.get('title', 'CS2 Skin')}\n\n"
            f"📤 **Send exactly** `{crypto_amount:.8g}` **{pay_display}** to:\n\n"
            f"📬 `{deposit_address}`{extra_id_text}\n\n"
            f"🎮 **Steam Trade URL:** Saved\n"
            f"🔄 **Status:** ⏳ Waiting for payment\n\n"
            f"_Once payment is confirmed, the admin will send your skin via Steam trade offer._",
            parse_mode="Markdown",
        )

    # Save SkinTransaction to database
    async with async_session() as session:
        # Get or create user
        stmt = select(User).where(User.telegram_id == user_id)
        result_db = await session.execute(stmt)
        user = result_db.scalar_one_or_none()

        if not user:
            user = User(telegram_id=user_id, username=username)
            session.add(user)
            await session.flush()

        skin_tx = SkinTransaction(
            user_id=user.id,
            dmarket_offer_id=offer_id,
            skin_name=item.get("title", "Unknown"),
            skin_price_usd=Decimal(str(round(markup_price_usd, 2))),
            pay_currency=pay_ticker,
            pay_network=pay_network,
            pay_amount=Decimal(str(crypto_amount)),
            deposit_address=deposit_address or "manual",
            changenow_id=changenow_id,
            steam_trade_url=steam_trade_url,
            status="payment_waiting",
            message_id=deposit_msg.message_id,
            chat_id=callback_query.message.chat.id,
        )
        session.add(skin_tx)
        await session.commit()

    # Log to Google Sheets
    try:
        import asyncio
        await asyncio.to_thread(
            log_action, user_id, username, "Skin Purchase Created",
            f"{item.get('title', 'Unknown')} | ${markup_price_usd:.2f} | {crypto_amount:.8g} {pay_display}"
        )
    except Exception as e:
        logger.warning(f"Failed to log skin purchase to sheets: {e}")

    await state.clear()
    await callback_query.answer()


@router.callback_query(SkinState.view_item, F.data == "skin_back_results")
async def back_to_results(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Go back to search results."""
    user_id = callback_query.from_user.id
    if not _is_test_user(user_id):
        return

    data = await state.get_data()
    query = data.get("search_query", "")
    items = data.get("search_items", [])
    offset = data.get("search_offset", 0)
    total = data.get("search_total", 0)

    if not items:
        # Re-fetch if items not in state
        result = await dmarket.search_items(title=query, limit=ITEMS_PER_PAGE, offset=offset)
        if "error" not in result:
            items = _parse_dmarket_items(result)
            total = result.get("total", {}).get("items", 0) if isinstance(result.get("total"), dict) else 0

    await callback_query.message.edit_text(
        f"🔫 **CS2 Skins — Results for \"{query}\"**\n"
        f"Found {total} items:\n",
        reply_markup=get_skin_results_keyboard(items, offset=offset, total=total, limit=ITEMS_PER_PAGE),
        parse_mode="Markdown",
    )
    await state.set_state(SkinState.browse_results)
    await callback_query.answer()


@router.callback_query(F.data == "cancel_skins")
async def cancel_skins(callback_query: types.CallbackQuery, state: FSMContext) -> None:
    """Cancel the skin purchase flow."""
    user_id = callback_query.from_user.id
    await state.clear()
    await callback_query.message.edit_text(
        "❌ Skin purchase cancelled.\n\n"
        "🟢 **Welcome to Nexi Exchange!**\n\n"
        "Choose an option below:",
        reply_markup=get_start_keyboard(user_id),
        parse_mode="Markdown",
    )
    await callback_query.answer()