import asyncio
import json
from app.clients.lex_runtime import LexRuntimeClient

async def run():
    client = LexRuntimeClient()
    response = await client.recognize_text(
        session_id="test-top-5-lex",
        text="Top 5 sản phẩm giá cao nhất"
    )
    print(json.dumps(response, indent=2, ensure_ascii=False))

asyncio.run(run())
