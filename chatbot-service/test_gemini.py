import asyncio
import os
from app.clients.gemini_client import GeminiClient

async def main():
    client = GeminiClient(api_key=os.environ.get("GEMINI_API_KEY"), enabled=True)
    res = await client.resolve_customer_intent_with_usage(
        lex_intent="fallbackintent",
        user_text="Iphone 12 giá"
    )
    print("RESULT:", res)

asyncio.run(main())
