import asyncio
from aiocryptopay import AioCryptoPay

async def main():
    crypto = AioCryptoPay('12345:test')
    try:
        res = await crypto.get_invoices(invoice_ids=123)
        print(type(res))
    except Exception as e:
        print(f"Error: {e}")

asyncio.run(main())
