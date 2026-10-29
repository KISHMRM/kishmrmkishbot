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
            # ۱. پیدا کردن آخرین تاریخ معاملاتی
            last_day_marker = "آخرین روز\n"
            last_day_index = text.find(last_day_marker)
            
            if last_day_index == -1:
                print("Could not find the last trading day.")
                return
                
            # تاریخ رو از خط بعد از "آخرین روز" برمی‌داریم (مثلاً ۱۴۰۵/۰۸/۰۹)
            last_date = text[last_day_index + len(last_day_marker):].split('\n')[0].strip()
            print(f"Last trading date found: {last_date}")

            # ۲. پیدا کردن بخش لیست انتقالات
            start_marker = "تازه‌ترین نقل و انتقالات"
            end_marker = "منبع: گزارش روزانه"
            
            start_index = text.find(start_marker)
            end_index = text.find(end_marker)
            
            if start_index != -1 and end_index != -1:
                transfers_text = text[start_index:end_index].strip()
                
                # پاک کردن کلمات اضافه اول لیست
                transfers_text = transfers_text.replace("تازه‌ترین نقل و انتقالات\nهمه\nخرید\nفروش\n", "")
                
                # تقسیم متن به خطوط
                lines = transfers_text.split('\n')
                
                # ۳. فیلتر کردن خطوط: فقط خطوطی که تاریخ آخرین روز رو دارن یا مربوط به همون رکورد هستن
                # چون هر رکورد چند خطی هست، ما بر اساس تاریخ فیلتر می‌کنیم
                # برای اینکه بفهمیم کدوم خطوط مربوط به یه رکورد هستن، از این روش استفاده می‌کنیم:
                
                final_records = []
                current_record = []
                
                for line in lines:
                    # اگر خط شامل تاریخ آخرین روز بود، یعنی رکورد جدید شروع شده
                    if last_date in line:
                        if current_record:
                            final_records.append(" | ".join(current_record))
                            current_record = []
                        current_record.append(line)
                    elif current_record:
                        current_record.append(line)
                        
                if current_record:
                    final_records.append(" | ".join(current_record))

                # ۴. ساخت پیام نهایی
                if final_records:
                    # جدا کردن رکوردها با خط جدید و علامت جداکننده
                    formatted_list = "\n➖➖➖➖➖➖➖➖\n".join(final_records)
                    message = f"<b>📊 نقل و انتقالات فاندبیس ({last_date})</b>\n\n{formatted_list}"
                    
                    # ارسال به تلگرام (با محدودیت کاراکتر)
                    max_length = 4000
                    if len(message) > max_length:
                        parts = [message[i:i+max_length] for i in range(0, len(message), max_length)]
                        for part in parts:
                            send_to_telegram(part)
                    else:
                        send_to_telegram(message)
                else:
                    print("No transfers found for the last date.")
            else:
                print("Could not find the specific markers in the page text.")
                
        except Exception as e:
            print("Error parsing text:", e)

if __name__ == "__main__":
    asyncio.run(main())
