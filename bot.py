import asyncio
import os
import re
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
                transfers_text = text[start_index:end_index].strip()
                lines = transfers_text.split('\n')
                clean_lines = [line.strip() for line in lines if line.strip() not in ["تازه‌ترین نقل و انتقالات", "همه", "خرید", "فروش"]]
                
                # جدا کردن بلوک‌های داده
                blocks = []
                current_block = []
                
                for line in clean_lines:
                    if last_date in line:
                        current_block.append(line)
                    elif current_block:
                        current_block.append(line)
                        if len(current_block) >= 4: # هر بلوک تقریبا ۴ خطه
                            blocks.append(current_block)
                            current_block = []
                
                if current_block:
                    blocks.append(current_block)

                # ۳. پردازش بلوک‌ها و تشخیص خرید و فروش
                buys = []
                sells = []

                for block in blocks:
                    block_text = " | ".join(block)
                    
                    # استخراج نام و نماد (اگر در انتهای بلوک باشه)
                    name_match = re.search(r'\|\s*(\d+)\s+(\S+)\s+(\d{4}/\d{2}/\d{2})\s*\|\s*(\d+)\s*\|\s*([^|]+)\s*\|', block_text)
                    player_name = ""
                    symbol_name = ""
                    if name_match:
                         symbol_name = name_match.group(2).strip()
                         player_name = name_match.group(5).strip()

                    # تشخیص خرید (افزایش) یا فروش (کاهش)
                    # اگر علامت + توی بلوک بود، خریده. اگر − بود، فروشه.
                    if any("+" in line or "‎+" in line for line in block):
                        # فرمت‌دهی خروجی برای خرید
                        formatted = f"🟢 <b>{player_name if player_name else 'خرید'}</b> | نماد: {symbol_name}\n{block[0]}"
                        buys.append(formatted)
                    elif any("−" in line or "-" in line for line in block):
                        formatted = f"🔴 <b>{player_name if player_name else 'فروش'}</b> | نماد: {symbol_name}\n{block[0]}"
                        sells.append(formatted)

                # ۴. ساخت پیام‌ها و ارسال
                if buys:
                    buy_msg = f"<b>🟢 خریدهای امروز ({last_date})</b>\n\n" + "\n➖➖➖➖➖➖➖➖\n".join(buys)
                    send_to_telegram(buy_msg)
                    await asyncio.sleep(2) # کمی صبر بین دو پیام

                if sells:
                    sell_msg = f"<b>🔴 فروش‌های امروز ({last_date})</b>\n\n" + "\n➖➖➖➖➖➖➖➖\n".join(sells)
                    send_to_telegram(sell_msg)
                
                if not buys and not sells:
                    print("No valid transfers found.")
            else:
                print("Could not find the specific markers in the page text.")
                
        except Exception as e:
            print("Error parsing text:", e)

if __name__ == "__main__":
    asyncio.run(main())
