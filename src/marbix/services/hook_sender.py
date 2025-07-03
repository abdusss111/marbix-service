import os
import asyncio
import httpx

WEBHOOK_URL  = "https://hook.eu2.make.com/21mxv813ce8it8ctzl7v7lqi7xrqheal"
MAKE_API_KEY = "NYYtTMIrRvYD27cSHIRXXgUcUKpn75MqTa4cufcQ41U"

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


async def main():
    data = {
        "business_type":        "IT  стартап",
        "business_goal":        "Увеличить продажи",
        "location":             "Алматы",
        "current_volume":       "5000 USD",            # <-- corrected key
        "product_data":         "AI-платформа для медицины",
        "target_audience_info": "Больницы, клиники",
        "competitors":          "ваап",                    # optional
        "actions":              "авпвап",                    # optional
        "marketing_budget":     "впвап"                     # optional
    }

    result = await push_to_webhook(data)

if __name__ == "__main__":
    asyncio.run(main())
