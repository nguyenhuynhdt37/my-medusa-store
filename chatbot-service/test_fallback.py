import asyncio
from app.clients.gemini_client import get_gemini_client

async def main():
    client = get_gemini_client()
    res = await client.generate_fallback_json_with_usage(user_text="chọn quà gì cho mẹ?")
    print(res)

asyncio.run(main())
