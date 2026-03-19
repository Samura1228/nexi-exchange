import aiohttp
import asyncio

async def main():
    async with aiohttp.ClientSession() as s:
        await s.post("http://example.com", headers={"x-api-key": None})

asyncio.run(main())
