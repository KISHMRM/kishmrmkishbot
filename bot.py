import asyncio
import os
import re
import requests
from playwright.async_api import async_playwright

URL = "https://app.fundbase.ir/"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

def send_to_telegram(text):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Error: Telegram credentials are not set in Secrets.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {"chat_id": CHAT_ID, "text": text, "parse_mode": "HTML"}
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
        # رفتن به صفحه اصلی
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        
        # صبر میکنیم تا صفحه اصلی کامل لود بشه
        await page.wait_for_timeout(3000)

        try:
            print("Looking for the funds trade section...")
            # پیدا کردن متن روی کارت و کلیک روی اون
            # از locator استفاده میکنیم تا مطمئن بشیم روی کارت درست کلیک میکنه
            target_card = page.locator("text=صندوق‌ها امروز چه سهم‌هایی خریدند و چه فروختند؟").first
            
            if await target_card.count() > 0:
                print("Found the card. Clicking...")
                await target_card.click()
                
                # صبر میکنیم تا پنجره (Modal) یا لیست باز بشه و دیتا لود بشه
                await page.wait_for_timeout(5000) 
                print("Clicked and waited.")
            else:
                print("Could not find the target section on the page.")
                await browser.close()
                return

            # حالا که کلیک کردیم، متن کل صفحه رو میخونیم (چون دیتا توی همون صفحه لود شده)
            text = await page.evaluate("document.body.innerText")
            await browser.close()

            # اینجا یک بخش از متن رو چاپ میکنیم تا ببینیم ساختارش چطوره
            print("Preview of loaded text after click:")
            print(text[:2000])

            # --- مرحله بعدی: تحلیل متن و ارسال ---
            # فعلاً برای تست، فقط یک پیام میفرستیم که ببینیم دیتا اومده یا نه
            message = f"<b>📊 تست باز شدن صندوق‌ها</b>\n\nبخش‌هایی از دیتای لود شده:\n\n{text[:1000]}"
            send_to_telegram(message)

        except Exception as e:
            print("Error:", e)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
