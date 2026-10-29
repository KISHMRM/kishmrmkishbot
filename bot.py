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
                    
                    # استخراج متن هر ستون
                    fund_name = (await cols[0].inner_text()).strip()
                    symbol = (await cols[1].inner_text()).strip()
                    
                    # در ستون ارزش، کلمه خرید/فروش و مبلغ با هم هستند. 
                    # ما کلمه خرید/فروش رو از مبلغ جدا میکنیم
                    value_col_text = (await cols[2].inner_text()).replace('\n', ' ').strip()
                    
                    asset_value = (await cols[3].inner_text()).replace('\n', ' ').strip()
                    weight_in_portfolio = (await cols[4].inner_text()).replace('\n', ' ').strip()
                    weight_30d = (await cols[5].inner_text()).replace('\n', ' ').strip()

                    # حذف فاصله‌های اضافی و خطوط جدید
                    import re
                    asset_value = re.sub(r'\s+', ' ', asset_value)
                    weight_in_portfolio = re.sub(r'\s+', ' ', weight_in_portfolio)
                    weight_30d = re.sub(r'\s+', ' ', weight_30d)

                    # ساخت متن پیام
                    formatted_record = (
                        f"🏢 <b>{fund_name}</b> | نماد: {symbol}\n"
                        f"💰 ارزش: {value_col_text}\n"
                        f"📊 دارایی: {asset_value} میلیارد تومان\n"
                        f"⚖️ وزن سبد: {weight_in_portfolio} | وزن ۳۰ روزه: {weight_30d}"
                    )

                    if "خرید" in value_col_text:
                        buys.append(formatted_record)
                    elif "فروش" in value_col_text:
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
