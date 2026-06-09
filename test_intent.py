import asyncio
from app.services.intent_service import extract_product_name_from_text

text = "iPhone 17 Pro Max giá bao nhiêu?"
print("Extracted:", extract_product_name_from_text(text))
