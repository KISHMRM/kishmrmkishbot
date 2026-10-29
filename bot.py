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
            # ۱. پیدا کردن آخرین تاریخ
            last_day_marker = "آخرین روز\n"
            last_day_index = text.find(last_day_marker)
            if last_day_index == -1:
                print("Could not find the last trading day.")
                return
            last_date = text[last_day_index + len(last_day_marker):].split('\n')[0].strip()
            print(f"Last trading date: {last_date}")

            # ۲. پیدا کردن بخش لیست انتقالات
            start_marker = "تازه‌ترین نقل و انتقالات"
            end_marker = "منبع: گزارش روزانه"
            
            start_index = text.find(start_marker)
            end_index = text.find(end_marker)
            
            if start_index != -1 and end_index != -1:
                # جدا کردن بخش انتقالات
                transfers_text = text[start_index:end_index].strip()
                
                # ۳. پاکسازی متن اولیه
                lines = transfers_text.split('\n')
                # حذف خطوط اول که شامل تیتر و دکمه هاست
                clean_lines = [line.strip() for line in lines if line.strip() not in ["تازه‌ترین نقل و انتقالات", "همه", "خرید", "فروش"]]
                
                # ۴. گروه‌بندی خطوط به صورت بلوک‌های متنی
                # چون هر کارت شامل چند خط هست، ما خطوط رو بررسی میکنیم
                # هر کارت معمولاً شامل نام و تاریخ هست که ما دنبال تاریخ میگردیم
                records = []
                current_record = []
                
                for line in clean_lines:
                    # اگر خط شامل تاریخ آخرین روز بود، یعنی یه رکورد جدید شروع شده
                    if last_date in line:
                        current_record.append(line)
                    elif current_record:
                        current_record.append(line)
                        # اگر به خطی رسیدیم که مربوط به رکورد بعدی نیست (مثل شروع کارت بعدی)
                        # و رکورد فعلی کامل شده، اون رو ذخیره میکنیم
                        # چون نمیدونیم دقیقا کجا تموم میشه، هر بار که یه تاریخ جدید دیدیم اون رو ذخیره میکنیم
                        if len(current_record) >= 4: # تعداد خطوط تقریبی هر کارت
                             records.append(" | ".join(current_record))
                             current_record = []

                # اگر آخرین رکورد جا مونده بود
                if current_record and len(current_record) > 0:
                    records.append(" | ".join(current_record))

                # حذف رکوردهای تکراری
                unique_records = list(dict.fromkeys(records))

                if unique_records:
                    formatted_list = "\n➖➖➖➖➖➖➖➖\n".join(unique_records)
                    message = f"<b>📊 نقل و انتقالات فاندبیس ({last_date})</b>\n\n{formatted_list}"
                    
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
