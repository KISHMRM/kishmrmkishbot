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
    payload = {"chat_id": CHAT_ID, "text": text} # parse_mode حذف شد تا مشکل فیلتر نداشته باشیم
    response = requests.post(url, json=payload)
    if response.status_code == 200:
        print("Message sent to Telegram successfully!")
    else:
        print("Failed to send message:", response.text)

def clean_text(text):
    # حذف فاصله های اضافی و خطوط جدید
    return re.sub(r'\s+', ' ', text).strip()

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
                    
                    # ستون ارزش (شامل کلمه خرید/فروش)
                    value_col_text = clean_text(await cols[2].inner_text())
                    
                    # ستون دارایی (معمولا دو عدد با فاصله داره)
                    asset_raw = clean_text(await cols[3].inner_text())
                    
                    # ستون وزن سبد (دو عدد با فاصله)
                    weight_raw = clean_text(await cols[4].inner_text())
                    
                    # ستون وزن ۳۰ روزه
                    weight_30d_raw = clean_text(await cols[5].inner_text())

                    # جدا کردن اعداد دارایی
                    asset_parts = asset_raw.split()
                    if len(asset_parts) >= 2:
                        asset_text = f"قبل: {asset_parts[0]} | بعد: {asset_parts[1]}"
                    else:
                        asset_text = asset_raw

                    # جدا کردن اعداد وزن سبد
                    weight_parts = weight_raw.split()
                    if len(weight_parts) >= 2:
                        weight_text = f"قبل: {weight_parts[0]} | بعد: {weight_parts[1]}"
                    else:
                        weight_text = weight_raw

                    formatted_record = (
                        f"🏢 {fund_name} | نماد: {symbol}\n"
                        f"💰 ارزش: {value_col_text}\n"
                        f"📊 دارایی: {asset_text} (میلیارد تومان)\n"
                        f"⚖️ وزن سبد: {weight_text}\n"
                        f"📅 وزن ۳۰ روزه: {weight_30d_raw}"
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
