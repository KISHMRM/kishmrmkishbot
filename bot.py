import asyncio
import os
import requests
from playwright.async_api import async_playwright

URL = "https://app.fundbase.ir/transfers"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_to_telegram(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Error: Telegram credentials are not set in Secrets.")
        return

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": text,
        "parse_mode": "HTML"
    }
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Message sent to Telegram successfully!")
    else:
        print("Failed to send message:", response.text)

async def main():
    print("Starting Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"Going to {URL}")
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        
        try:
            await page.wait_for_selector("table", timeout=15000)
            print("Table found!")
        except Exception:
            print("Table not found.")
            await browser.close()
            return

        text = await page.evaluate("document.body.innerText")
        await browser.close()

        try:
            start_marker = "خلاصه آخرین روز معاملاتی"
            end_marker = "اشخاص حقیقی به دلیل مشخص نبودن"
            
            start_index = text.find(start_marker)
            end_index = text.find(end_marker)
            
            if start_index != -1 and end_index != -1:
                summary_text = text[start_index:end_index].strip()
                message = f"<b>📊 گزارش نقل و انتقالات فاندبیس</b>\n\n{summary_text}"
                send_to_telegram(message)
            else:
                print("Could not find the specific markers in the page text.")
                
        except Exception as e:
            print("Error parsing text:", e)

if __name__ == "__main__":
    asyncio.run(main())
