import httpx
import asyncio

async def test():
    async with httpx.AsyncClient() as c:
        r = await c.get('http://127.0.0.1:8001/health')
        print(r.status_code, r.json())

asyncio.run(test())