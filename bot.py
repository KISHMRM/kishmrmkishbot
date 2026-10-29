import asyncio
import os
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
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        await page.wait_for_timeout(3000)

        try:
            print("Looking for the funds trade section...")
            target_card = page.locator("text=صندوق‌ها امروز چه سهم‌هایی خریدند و چه فروختند؟").first
            
            if await target_card.count() > 0:
                print("Found the card. Clicking...")
                await target_card.click()
                # صبر برای باز شدن جدول
                await page.wait_for_timeout(5000) 
                
                # پیدا کردن جدول اصلی
                table = page.locator("table").first
                if await table.count() == 0:
                    print("Table not found!")
                    await browser.close()
                    return

                # گرفتن تمام ردیف های جدول
                rows = await table.locator("tr").all()
                print(f"Found {len(rows)} rows in table.")

                buys = []
                sells = []

                # از ردیف دوم شروع میکنیم چون ردیف اول هدر (تیتر) جدول است
                for row in rows[1:]:
                    cols = await row.locator("td").all()
                    if len(cols) < 6:
                        continue # اگر ردیف ستون کافی نداشت رد میشیم
                    
                    # استخراج متن هر ستون
                    fund_name = (await cols[0].inner_text()).strip()
                    symbol = (await cols[1].inner_text()).strip()
                    value_text = (await cols[2].inner_text()).strip().replace('\n', ' ') # شامل کلمه خرید/فروش و مبلغ
                    asset_value = (await cols[3].inner_text()).strip().replace('\n', ' ')
                    weight_in_portfolio = (await cols[4].inner_text()).strip().replace('\n', ' ')
                    weight_30d = (await cols[5].inner_text()).strip().replace('\n', ' ')

                    # فرمت‌دهی به شکل خوانا
                    formatted_record = (
                        f"🏢 <b>صندوق:</b> {fund_name}\n"
                        f"📈 <b>نماد:</b> {symbol}\n"
                        f"💰 <b>ارزش:</b> {value_text}\n"
                        f"📊 <b>دارایی:</b> {asset_value}\n"
                        f"⚖️ <b>وزن سبد:</b> {weight_in_portfolio} | <b>وزن ۳۰ روزه:</b> {weight_30d}"
                    )

                    # تفکیک خرید و فروش بر اساس وجود کلمه در ستون ارزش
                    if "خرید" in value_text:
                        buys.append(formatted_record)
                    elif "فروش" in value_text:
                        sells.append(formatted_record)

                # ارسال به تلگرام
                if buys:
                    buy_msg = "<b>🟢 خریدهای صندوق‌ها</b>\n\n" + "\n➖➖➖➖➖➖➖➖\n".join(buys)
                    send_to_telegram(buy_msg)
                    await asyncio.sleep(2)
                
                if sells:
                    sell_msg = "<b>🔴 فروش‌های صندوق‌ها</b>\n\n" + "\n➖➖➖➖➖➖➖➖\n".join(sells)
                    send_to_telegram(sell_msg)

                if not buys and not sells:
                    print("No data could be extracted from the table.")

            else:
                print("Could not find the target section on the page.")

        except Exception as e:
            print("Error:", e)
        finally:
            await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
