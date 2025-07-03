import os
import asyncio
import httpx
from dotenv import load_dotenv
load_dotenv()
WEBHOOK_URL  = os.environ.get("WEBHOOK_URL")
MAKE_API_KEY = os.environ.get("MAKE_API_KEY")
async def push_to_webhook(payload: dict) -> dict | str:
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(
            WEBHOOK_URL,
            headers={
                "Content-Type":  "application/json",
                "x-make-apikey": MAKE_API_KEY,
            },
            json=payload
        )
        resp.raise_for_status()

        body = resp.text.strip()
        if not body:
            # empty response from webhook
            return {}  # or return "OK" if you prefer
        # if it’s valid JSON, parse; otherwise return raw text
        try:
            return resp.json()
        except ValueError:
            return body


