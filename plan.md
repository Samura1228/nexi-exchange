Ч# Nexi Exchange Bot - Implementation Plan

## Overview
A fully functional, non-custodial cryptocurrency exchange Telegram bot named "Nexi Exchange". It allows users to swap cryptocurrencies automatically using the ChangeNow API.

## Features
- **Currencies**: Limited to top popular coins for a clean UI (BTC, ETH, SOL, TON, USDT-TRC20, USDT-ERC20, LTC, XRP, TRX).
- **Real-time Rates**: Fetches live exchange rates from ChangeNow.
- **Automatic Status Updates**: The bot automatically polls the transaction status and updates the chat message (Waiting -> Confirming -> Exchanging -> Sending -> Finished).
- **Minimalistic UI**: Uses Emojis (🟢/🔴) for visual cues instead of custom CSS.

## Tech Stack
- **Language**: Python 3.10+
- **Framework**: `aiogram` (v3.x)
- **HTTP Client**: `aiohttp`
- **API**: ChangeNow.io

## Configuration
- **Bot Token**: `8691711199:AAE_DSlAukrGTkkxq3AfUvqlYi12BeC9Zu4`
- **ChangeNow API Key**: `2118a1f5f7cc5c5aa1cb7b25472194011222f8b5296e23e0828c125673589de2`

## File Structure
- `main.py`: Application entry point.
- `config.py`: Configuration loader.
- `services/changenow.py`: Wrapper for ChangeNow API.
- `handlers/exchange.py`: Main logic for the exchange flow.
- `keyboards/builders.py`: Helper for creating inline keyboards.
- `utils/states.py`: FSM State definitions.

## User Flow
1. **/start**: Welcome message with "🟢 Start Exchange".
2. **Select Currency**: User selects source (From) and destination (To) currencies.
3. **Enter Amount**: User inputs amount. Bot validates against minimum requirement.
4. **Enter Address**: User inputs destination wallet address.
5. **Confirm**: User reviews details and confirms.
6. **Deposit**: Bot provides a deposit address.
7. **Tracking**: Bot updates the message status automatically until completion.