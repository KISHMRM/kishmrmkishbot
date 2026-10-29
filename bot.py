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
        await page.wait_for_timeout(3000) 

        try:
            page_text = await page.evaluate("document.body.innerText")
            last_day_marker = "آخرین روز\n"
            last_day_index = page_text.find(last_day_marker)
            if last_day_index == -1:
                print("Could not find the last trading day.")
                await browser.close()
                return
            last_date = page_text[last_day_index + len(last_day_marker):].split('\n')[0].strip()
            print(f"Last trading date: {last_date}")

            # ۱. پیدا کردن دقیق کارت های لیست پایین صفحه
            # سایت فاندبیس معمولا هر کارت رو داخل یه تگ با کلاس خاص میذاره. 
            # ما اینجا تمام دیو هایی رو میگیریم که کلاسشون شامل کلمه 'rounded' یا 'border' هست
            cards = await page.locator("div.rounded-xl:has-text('مالکیت'), div[class*='card']:has-text('مالکیت')").all()
            
            # اگر پیدا نکرد، از یه روش دیگه استفاده میکنیم که دقیق تر باشه
            if not cards:
                # پیدا کردن بلوک های اصلی که شامل یک تاریخ معتبر و کلمه مالکیت هستن
                cards = await page.locator("div:has-text('مالکیت'):not(:has(div:has-text('مالکیت')))").all()

            buys = []
            sells = []
            seen_names = set() # برای جلوگیری از تکرار

            for card in cards:
                card_text = await card.inner_text()
                if last_date not in card_text:
                    continue
                    
                lines = [line.strip() for line in card_text.split('\n') if line.strip()]
                
                # پیدا کردن نام بازیکن (خطی که معمولا اولین خطه و عدد نداره)
                player_name = "نامشخص"
                for line in lines:
                    if not any(char.isdigit() for char in line) and "خرید" not in line and "فروش" not in line and "مالکیت" not in line:
                        player_name = line
                        break
                
                # پیدا کردن نماد (کلمه ای که دقیقا بعد از "افزایش" یا "کاهش" میاد)
                symbol_name = "نامشخص"
                for i, line in enumerate(lines):
                    if "افزایش" in line or "کاهش" in line:
                        if i + 1 < len(lines):
                            symbol_name = lines[i+1]
                        break
                
                # پیدا کردن مقدار سهم
                share_amount = next((l for l in lines if "سهم" in l), "")
                
                # پیدا کردن درصد مالکیت
                ownership = next((l for l in lines if "مالکیت" in l), "")
                
                # پیدا کردن ارزش ریالی
                value = next((l for l in lines if "میلیارد تومان" in l or "میلیون تومان" in l or "هزار تومان" in l), "")

                # اگر اسم پیدا نشد یا تکراری بود، نادیده بگیر
                if player_name == "نامشخص":
                    continue
                if player_name in seen_names:
                    continue
                seen_names.add(player_name)

                if "افزایش" in card_text or "+" in card_text:
                    formatted = f"🟢 <b>{player_name}</b> | نماد: {symbol_name}\n💰 {value}\n📊 {share_amount} | {ownership}"
                    buys.append(formatted)
                elif "کاهش" in card_text or "−" in card_text or "-" in card_text:
                    formatted = f"🔴 <b>{player_name}</b> | نماد: {symbol_name}\n💰 {value}\n📊 {share_amount} | {ownership}"
                    sells.append(formatted)

            # ۳. ارسال به تلگرام
            if buys:
                buy_msg = f"<b>🟢 خریدهای امروز ({last_date})</b>\n\n" + "\n➖➖➖➖➖➖➖➖\n".join(buys)
                send_to_telegram(buy_msg)
                await asyncio.sleep(2)
            else:
                print("No buys found.")

            if sells:
                sell_msg = f"<b>🔴 فروش‌های امروز ({last_date})</b>\n\n" + "\n➖➖➖➖➖➖➖➖\n".join(sells)
                send_to_telegram(sell_msg)
            else:
                print("No sells found.")

        except Exception as e:
            print("Error:", e)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
