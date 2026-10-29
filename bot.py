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
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000) # کمی صبر میکنیم تا کارت ها لود شن
        
        try:
            # ۱. پیدا کردن آخرین تاریخ
            page_text = await page.evaluate("document.body.innerText")
            last_day_marker = "آخرین روز\n"
            last_day_index = page_text.find(last_day_marker)
            if last_day_index == -1:
                print("Could not find the last trading day.")
                await browser.close()
                return
            last_date = page_text[last_day_index + len(last_day_marker):].split('\n')[0].strip()
            print(f"Last trading date: {last_date}")

            # ۲. استخراج کارت‌های نقل و انتقالات
            # ما دنبال کارت هایی میگردیم که متنشون شامل کلمه "مالکیت سهم" هست (چون توی همه کارت ها هست)
            cards = await page.locator("div:has-text('مالکیت سهم')").all()
            
            records = []
            for card in cards:
                text = await card.inner_text()
                # اگر تاریخ آخرین روز توی این کارت بود، یعنی مربوط به امروزه
                if last_date in text and "تومان" in text and "میلیون" in text:
                    # پاکسازی متن کارت برای نمایش بهتر
                    clean_text = text.replace('\n', ' | ').strip()
                    # حذف کاراکترهای اضافی
                    records.append(clean_text)

            # ۳. ساخت پیام و ارسال
            if records:
                # برای جلوگیری از تکراری بودن کارت های والد، از set استفاده می‌کنیم
                unique_records = list(dict.fromkeys(records))
                
                formatted_list = "\n➖➖➖➖➖➖➖➖\n".join(unique_records)
                message = f"<b>📊 نقل و انتقالات فاندبیس ({last_date})</b>\n\n{formatted_list}"
                
                # تقسیم پیام طولانی
                max_length = 4000
                if len(message) > max_length:
                    parts = [message[i:i+max_length] for i in range(0, len(message), max_length)]
                    for part in parts:
                        send_to_telegram(part)
                else:
                    send_to_telegram(message)
            else:
                print("No transfers found for the last date.")
                
        except Exception as e:
            print("Error:", e)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
