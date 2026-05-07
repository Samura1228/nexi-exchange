# locales/texts.py

TEXTS = {
    "en": {
        # Main menu
        "welcome": "🟢 **Welcome to Nexi Exchange!**\n\nSwap cryptocurrencies instantly — non-custodial, fast, and secure.\n\nChoose an option below:",
        "welcome_back": "🟢 **Welcome back!**\n\nChoose an option below:",
        "main_menu": "Choose an option below:",

        # Buttons
        "btn_exchange": "🟢 Start Exchange",
        "btn_history": "📋 My Exchanges",
        "btn_referrals": "👥 Referrals",
        "btn_support": "💬 Support",
        "btn_settings": "⚙️ Settings",
        "btn_skins": "🔫 Buy CS2 Skins",
        "btn_cancel": "❌ Cancel",
        "btn_back": "🔙 Back to Menu",
        "btn_confirm": "✅ Confirm Exchange",
        "btn_my_id": "🆔 My Account ID",
        "btn_language": "🌐 Language",
        "btn_share_referral": "📤 Share Referral Link",
        "btn_new_search": "🔍 New Search",
        "btn_back_results": "⬅️ Back to Results",
        "btn_confirm_purchase": "✅ Confirm Purchase",
        "btn_cancel_support": "🔙 Cancel",

        # Exchange flow
        "select_from": "💱 **Select the currency you want to send (FROM):**",
        "select_to": "💱 **Sending:** {from_display}\n\n**Select the currency you want to receive (TO):**",
        "fetching_details": "⏳ Fetching exchange details for {from_display} → {to_display}...",
        "pair_unavailable": "❌ This exchange pair is currently unavailable.\n\nError: {error}\n\nPlease try a different pair.",
        "enter_amount": "💱 **{from_display} → {to_display}**\n\nEnter the amount of **{from_display}** you want to exchange:\n\n_(Minimum: {min_amount} {from_display})_",
        "invalid_amount": "❌ Please enter a valid positive number.",
        "amount_below_min": "❌ Amount is below the minimum of {min_amount} {from_display}.\nPlease enter a larger amount.",
        "getting_rate": "⏳ Getting exchange rate for {amount} {from_display} → {to_display}...",
        "rate_error": "❌ Could not get exchange rate.\n\nError: {error}\n\nPlease try again.",
        "estimate_too_small": "❌ The estimated amount is too small. Please try a larger amount.",
        "exchange_quote": "💱 **Exchange Quote:**\n\n📤 **You send:** {amount} {from_display}\n📥 **You get:** ~{displayed_estimate} {to_display}\n\nNow enter your **{to_display}** destination wallet address:",
        "invalid_address": "❌ That doesn't look like a valid wallet address. Please try again.",
        "confirm_exchange": "📋 **Exchange Confirmation:**\n\n📤 **Send:** {amount} {from_display}\n📥 **Receive:** ~{displayed_estimate} {to_display}\n📬 **To address:** `{address}`\n\n⚠️ Please verify the address carefully. Transactions cannot be reversed.\n\nPress **Confirm** to proceed or **Cancel** to abort.",
        "creating_exchange": "⏳ Creating your exchange...",
        "exchange_create_error": "❌ Failed to create exchange.\n\nError: {error}\n\nPlease try again.",
        "exchange_unexpected_error": "❌ Unexpected response from exchange service. Please try again.",
        "exchange_created": "✅ **Exchange Created!**\n\n📤 **Send exactly** `{amount}` **{from_display}** to:\n\n📬 `{deposit_address}`{extra_id_text}\n\n📥 **You will receive:** ~{displayed_estimate} {to_display}\n📬 **To:** `{address}`\n\n🔄 **Status:** ⏳ Waiting for deposit\n🆔 **Exchange ID:** `{changenow_id}`\n\n⏳ Time remaining: {timer}\n\n⚠️ Send within 1 hour or the exchange will be cancelled.",
        "exchange_memo": "\n🏷️ **Memo/Tag:** `{memo}`",
        "exchange_cancelled": "❌ Exchange cancelled.\n\n🟢 **Welcome to Nexi Exchange!**\n\nChoose an option below:",

        # Status
        "status_waiting": "⏳ Waiting for deposit",
        "status_confirming": "🔍 Confirming transaction...",
        "status_exchanging": "🔄 Exchanging...",
        "status_sending": "📤 Sending to your wallet...",
        "status_finished": "✅ Exchange complete! You received {amount} {currency}",
        "status_failed": "❌ Exchange failed. Please contact support.",
        "status_refunded": "↩️ Exchange refunded.",
        "status_expired": "⏰ Exchange expired. No deposit received.",
        "timer_remaining": "⏳ Time remaining: {minutes}:{seconds:02d}",
        "timer_warning": "\n\n⚠️ Send within 1 hour or the exchange will be cancelled.",
        "timer_expired": "⏰ Exchange expired. No deposit received within 1 hour.",

        # Referrals
        "referral_title": "👥 **Your Referral Dashboard**\n\n🔗 **Your referral link:**\n`{referral_link}`\n\n📊 **Stats:**\n├ 👤 Referrals: **{referral_count}**\n└ 💰 Total earned: **{earnings_str} USDT**\n\n💡 Share your link with friends! You earn **20%** of the exchange fee every time your referral makes a swap.\n\n_Tap the button below to share your link:_",
        "referral_share_text": "🟢 Try Nexi Exchange — swap crypto instantly, non-custodial and secure!\n👉 {referral_link}",
        "referral_new": "🎉 Someone joined via your referral link!\nYou now have **{count}** referral(s).",
        "referral_earned": "💸 You earned **{amount} {currency}** from a referral exchange!\nTotal referral earnings: **{total} USDT**",
        "referral_user_not_found": "❌ User not found. Please /start the bot first.",

        # Support
        "support_prompt": "📝 **Please describe your issue.**\n\nType your message below (text, photo, or document):",
        "support_sent": "✅ Your message has been sent to support. We'll reply shortly!",
        "support_reply_header": "💬 **Support reply:**\n\n{text}",

        # History
        "history_title": "📋 **My Recent Exchanges:**\n\n",
        "history_empty": "📋 **My Exchanges**\n\nNo exchanges found. Start your first exchange!",

        # Settings
        "settings_title": "⚙️ **Settings**\n\nYour ID: `{user_id}`\nLanguage: {language}\n\nChoose an option:",
        "language_changed": "✅ Language changed to English 🇬🇧",
        "choose_language": "🌐 **Choose your language:**",

        # Language names
        "lang_en": "🇬🇧 English",
        "lang_ru": "🇷🇺 Русский",

        # Errors
        "error_generic": "❌ Something went wrong. Please try again.",
    },

    "ru": {
        # Main menu
        "welcome": "🟢 **Добро пожаловать в Nexi Exchange!**\n\nМгновенный обмен криптовалют — некастодиальный, быстрый и безопасный.\n\nВыберите действие:",
        "welcome_back": "🟢 **С возвращением!**\n\nВыберите действие:",
        "main_menu": "Выберите действие:",

        # Buttons
        "btn_exchange": "🟢 Начать обмен",
        "btn_history": "📋 Мои обмены",
        "btn_referrals": "👥 Рефералы",
        "btn_support": "💬 Поддержка",
        "btn_settings": "⚙️ Настройки",
        "btn_skins": "🔫 Купить скины CS2",
        "btn_cancel": "❌ Отмена",
        "btn_back": "🔙 Назад в меню",
        "btn_confirm": "✅ Подтвердить обмен",
        "btn_my_id": "🆔 Мой ID",
        "btn_language": "🌐 Язык",
        "btn_share_referral": "📤 Поделиться ссылкой",
        "btn_new_search": "🔍 Новый поиск",
        "btn_back_results": "⬅️ К результатам",
        "btn_confirm_purchase": "✅ Подтвердить покупку",
        "btn_cancel_support": "🔙 Отмена",

        # Exchange flow
        "select_from": "💱 **Выберите валюту для отправки (ИЗ):**",
        "select_to": "💱 **Отправляете:** {from_display}\n\n**Выберите валюту для получения (В):**",
        "fetching_details": "⏳ Получаем данные обмена {from_display} → {to_display}...",
        "pair_unavailable": "❌ Эта пара обмена сейчас недоступна.\n\nОшибка: {error}\n\nПопробуйте другую пару.",
        "enter_amount": "💱 **{from_display} → {to_display}**\n\nВведите сумму **{from_display}** для обмена:\n\n_(Минимум: {min_amount} {from_display})_",
        "invalid_amount": "❌ Пожалуйста, введите корректное положительное число.",
        "amount_below_min": "❌ Сумма ниже минимума {min_amount} {from_display}.\nВведите большую сумму.",
        "getting_rate": "⏳ Получаем курс обмена для {amount} {from_display} → {to_display}...",
        "rate_error": "❌ Не удалось получить курс обмена.\n\nОшибка: {error}\n\nПопробуйте ещё раз.",
        "estimate_too_small": "❌ Расчётная сумма слишком мала. Попробуйте большую сумму.",
        "exchange_quote": "💱 **Расчёт обмена:**\n\n📤 **Вы отправляете:** {amount} {from_display}\n📥 **Вы получите:** ~{displayed_estimate} {to_display}\n\nВведите адрес вашего **{to_display}** кошелька:",
        "invalid_address": "❌ Это не похоже на валидный адрес кошелька. Попробуйте ещё раз.",
        "confirm_exchange": "📋 **Подтверждение обмена:**\n\n📤 **Отправить:** {amount} {from_display}\n📥 **Получить:** ~{displayed_estimate} {to_display}\n📬 **На адрес:** `{address}`\n\n⚠️ Проверьте адрес внимательно. Транзакции необратимы.\n\nНажмите **Подтвердить** или **Отмена**.",
        "creating_exchange": "⏳ Создаём ваш обмен...",
        "exchange_create_error": "❌ Не удалось создать обмен.\n\nОшибка: {error}\n\nПопробуйте ещё раз.",
        "exchange_unexpected_error": "❌ Неожиданный ответ от сервиса обмена. Попробуйте ещё раз.",
        "exchange_created": "✅ **Обмен создан!**\n\n📤 **Отправьте ровно** `{amount}` **{from_display}** на:\n\n📬 `{deposit_address}`{extra_id_text}\n\n📥 **Вы получите:** ~{displayed_estimate} {to_display}\n📬 **На:** `{address}`\n\n🔄 **Статус:** ⏳ Ожидание депозита\n🆔 **ID обмена:** `{changenow_id}`\n\n⏳ Осталось времени: {timer}\n\n⚠️ Отправьте в течение 1 часа, иначе обмен будет отменён.",
        "exchange_memo": "\n🏷️ **Мемо/Тег:** `{memo}`",
        "exchange_cancelled": "❌ Обмен отменён.\n\n🟢 **Добро пожаловать в Nexi Exchange!**\n\nВыберите действие:",

        # Status
        "status_waiting": "⏳ Ожидание депозита",
        "status_confirming": "🔍 Подтверждение транзакции...",
        "status_exchanging": "🔄 Обмен в процессе...",
        "status_sending": "📤 Отправка на ваш кошелёк...",
        "status_finished": "✅ Обмен завершён! Вы получили {amount} {currency}",
        "status_failed": "❌ Обмен не удался. Обратитесь в поддержку.",
        "status_refunded": "↩️ Средства возвращены.",
        "status_expired": "⏰ Обмен истёк. Депозит не получен.",
        "timer_remaining": "⏳ Осталось времени: {minutes}:{seconds:02d}",
        "timer_warning": "\n\n⚠️ Отправьте в течение 1 часа, иначе обмен будет отменён.",
        "timer_expired": "⏰ Обмен истёк. Депозит не получен в течение 1 часа.",

        # Referrals
        "referral_title": "👥 **Ваша реферальная программа**\n\n🔗 **Ваша реферальная ссылка:**\n`{referral_link}`\n\n📊 **Статистика:**\n├ 👤 Рефералов: **{referral_count}**\n└ 💰 Заработано: **{earnings_str} USDT**\n\n💡 Делитесь ссылкой с друзьями! Вы получаете **20%** комиссии с каждого обмена ваших рефералов.\n\n_Нажмите кнопку ниже, чтобы поделиться:_",
        "referral_share_text": "🟢 Попробуйте Nexi Exchange — мгновенный обмен крипты, безопасно и надёжно!\n👉 {referral_link}",
        "referral_new": "🎉 Кто-то присоединился по вашей реферальной ссылке!\nУ вас теперь **{count}** реферал(ов).",
        "referral_earned": "💸 Вы заработали **{amount} {currency}** с обмена реферала!\nВсего реферальных: **{total} USDT**",
        "referral_user_not_found": "❌ Пользователь не найден. Сначала нажмите /start.",

        # Support
        "support_prompt": "📝 **Опишите вашу проблему.**\n\nНапишите сообщение ниже (текст, фото или документ):",
        "support_sent": "✅ Ваше сообщение отправлено в поддержку. Мы ответим в ближайшее время!",
        "support_reply_header": "💬 **Ответ поддержки:**\n\n{text}",

        # History
        "history_title": "📋 **Ваши последние обмены:**\n\n",
        "history_empty": "📋 **Мои обмены**\n\nОбменов не найдено. Начните свой первый обмен!",

        # Settings
        "settings_title": "⚙️ **Настройки**\n\nВаш ID: `{user_id}`\nЯзык: {language}\n\nВыберите действие:",
        "language_changed": "✅ Язык изменён на Русский 🇷🇺",
        "choose_language": "🌐 **Выберите язык:**",

        # Language names
        "lang_en": "🇬🇧 English",
        "lang_ru": "🇷🇺 Русский",

        # Errors
        "error_generic": "❌ Что-то пошло не так. Попробуйте ещё раз.",
    }
}


def get_text(key: str, lang: str = "en", **kwargs) -> str:
    """Get localized text by key. Falls back to English if key not found."""
    text = TEXTS.get(lang, TEXTS["en"]).get(key, TEXTS["en"].get(key, key))
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text