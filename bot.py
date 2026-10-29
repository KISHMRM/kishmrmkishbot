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
    payload = {"chat_id": CHAT_ID, "text": text}
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Message sent to Telegram successfully!")
    else:
        print("Failed to send message:", response.text)

def clean_text(text):
    return re.sub(r'\s+', ' ', text).strip()

def parse_two_numbers(text):
    """اگر متن شامل دو عدد بود، آن‌ها را با برچسب قبل و بعد جدا میکند"""
    parts = text.split()
    if len(parts) >= 2:
        # اگر علامتهایی مثل — یا · وجود داشت، فقط اعداد معتبر را در نظر بگیر
        valid_parts = [p for p in parts if any(char.isdigit() for char in p)]
        if len(valid_parts) >= 2:
            return f"قبل: {valid_parts[0]} | بعد: {valid_parts[1]}"
    return text

async def main():
    print("Starting Playwright...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"Going to {URL}")
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        try:
            print("Looking for the funds trade section...")
            target_card = page.locator("text=صندوق‌ها امروز چه سهم‌هایی خریدند و چه فروختند؟").first
            
            if await target_card.count() > 0:
                print("Found the card. Clicking...")
                await target_card.click()
                await page.wait_for_timeout(5000) 
                
                table = page.locator("table").first
                if await table.count() == 0:
                    print("Table not found!")
                    await browser.close()
                    return

                rows = await table.locator("tr").all()
                print(f"Found {len(rows)} rows in table.")

                buys = []
                sells = []

                for row in rows[1:]:
                    cols = await row.locator("td").all()
                    if len(cols) < 6:
                        continue
                    
                    fund_name = clean_text(await cols[0].inner_text())
                    symbol = clean_text(await cols[1].inner_text())
                    value_col_text = clean_text(await cols[2].inner_text())
                    
                    asset_raw = clean_text(await cols[3].inner_text())
                    weight_raw = clean_text(await cols[4].inner_text())
                    weight_30d_raw = clean_text(await cols[5].inner_text())

                    # پردازش اعداد با تابع جدید
                    asset_text = parse_two_numbers(asset_raw)
                    weight_text = parse_two_numbers(weight_raw)
                    weight_30d_text = parse_two_numbers(weight_30d_raw)

                    formatted_record = (
                        f"🏢 {fund_name} | نماد: {symbol}\n"
                        f"💰 ارزش: {value_col_text}\n"
                        f"📊 دارایی: {asset_text} (میلیارد تومان)\n"
                        f"⚖️ وزن سبد: {weight_text}\n"
                        f"📅 وزن ۳۰ روزه: {weight_30d_text}"
                    )

                    if "خرید" in value_col_text:
                        buys.append(formatted_record)
                    elif "فروش" in value_col_text:
                        sells.append(formatted_record)

                # ارسال به تلگرام
                if buys:
                    buy_msg = "🟢 خریدهای صندوق‌ها\n\n" + "\n➖➖➖➖➖➖➖➖\n".join(buys)
                    send_to_telegram(buy_msg)
                    await asyncio.sleep(2)
                
                if sells:
                    sell_msg = "🔴 فروش‌های صندوق‌ها\n\n" + "\n➖➖➖➖➖➖➖➖\n".join(sells)
                    send_to_telegram(sell_msg)

            else:
                print("Could not find the target section on the page.")

        except Exception as e:
            print("Error:", e)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
