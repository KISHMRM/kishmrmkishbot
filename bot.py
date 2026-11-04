import asyncio
import logging
import os
import re
from datetime import datetime
from zoneinfo import ZoneInfo

import requests
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError

URL = "https://app.fundbase.ir/"
SECTION_TITLE = "صندوق‌ها امروز چه سهم‌هایی خریدند و چه فروختند؟"
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
TEHRAN_TZ = ZoneInfo("Asia/Tehran")
MESSAGE_LIMIT = 3500

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def clean_text(value):
    return re.sub(r"\s+", " ", value or "").strip()


def send_to_telegram(message):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        raise RuntimeError("TELEGRAM_TOKEN یا CHAT_ID در GitHub Secrets تنظیم نشده است.")

    endpoint = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    response = requests.post(
        endpoint,
        json={"chat_id": CHAT_ID, "text": message, "disable_web_page_preview": True},
        timeout=30,
    )
    try:
        payload = response.json()
    except ValueError:
        payload = {}

    if not response.ok or not payload.get("ok"):
        description = payload.get("description", response.text[:500])
        raise RuntimeError(f"ارسال پیام تلگرام ناموفق بود: {description}")


def split_message(text, limit=MESSAGE_LIMIT):
    if len(text) <= limit:
        return [text]

    chunks = []
    current = ""
    for paragraph in text.split("\n"):
        candidate = paragraph if not current else current + "\n" + paragraph
        if len(candidate) <= limit:
            current = candidate
            continue
        if current:
            chunks.append(current)
            current = ""
        while len(paragraph) > limit:
            chunks.append(paragraph[:limit])
            paragraph = paragraph[limit:]
        current = paragraph

    if current:
        chunks.append(current)
    return chunks


def format_value_cell(value):
    # فقط متن مربوط به ارزش معامله را نگه می‌داریم و برچسب خرید/فروش را حذف می‌کنیم.
    lines = [
        clean_text(line)
        for line in (value or "").splitlines()
        if clean_text(line) and clean_text(line) not in ("خرید", "فروش")
    ]
    value_text = "\n".join(lines).strip()
    if not value_text:
        raise RuntimeError("مقدار ارزش خرید/فروش در یکی از ردیف‌ها خالی است.")

    if "میلیارد تومان" in value_text:
        if "ارزش خرید" not in value_text and "ارزش فروش" not in value_text and "ارزش خرید / فروش" not in value_text:
            return "ارزش خرید / فروش\n" + value_text
        return value_text

    # در صورتی که سلول فقط عدد را داشته باشد.
    return f"ارزش خرید / فروش\nمیلیارد تومان: {value_text}"


async def extract_trades():
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch(headless=True)
        page = await browser.new_page(locale="fa-IR")
        try:
            logger.info("Opening %s", URL)
            await page.goto(URL, wait_until="domcontentloaded", timeout=60000)
            try:
                await page.wait_for_load_state("networkidle", timeout=15000)
            except PlaywrightTimeoutError:
                logger.info("Page did not become network-idle; continuing.")

            section = page.get_by_text(SECTION_TITLE, exact=True).first
            if await section.count() == 0:
                raise RuntimeError("بخش معاملات صندوق‌ها در صفحه پیدا نشد.")

            await section.scroll_into_view_if_needed()
            try:
                await section.click(timeout=15000)
                logger.info("Clicked the fund trades section.")
            except PlaywrightTimeoutError:
                logger.info("Section click timed out; checking whether its table is already visible.")

            try:
                await page.wait_for_function(
                    "() => Array.from(document.querySelectorAll('table')).some(t => t.querySelectorAll('tr').length > 1)",
                    timeout=20000,
                )
            except PlaywrightTimeoutError:
                pass

            tables = page.locator("table")
            table_count = await tables.count()
            if table_count == 0:
                raise RuntimeError("بخش پیدا شد، اما هیچ جدول معاملاتی بارگذاری نشد.")

            trades = {"buy": [], "sell": []}
            seen = set()

            for table_index in range(table_count):
                table = tables.nth(table_index)
                rows = table.locator("tr")
                row_count = await rows.count()
                if row_count < 2:
                    continue

                for row_index in range(1, row_count):
                    cells = await rows.nth(row_index).locator("th, td").all_inner_texts()
                    values = [clean_text(cell) for cell in cells]
                    if len(values) < 3:
                        continue

                    row_text = " | ".join(values)
                    is_buy = "خرید" in row_text
                    is_sell = "فروش" in row_text
                    if is_buy == is_sell:
                        continue

                    trade_type = "buy" if is_buy else "sell"
                    key = (trade_type, tuple(values[:3]))
                    if key in seen:
                        continue
                    seen.add(key)

                    fund_name = values[0]
                    symbol = values[1]
                    value_text = format_value_cell(await rows.nth(row_index).locator("th, td").nth(2).inner_text())

                    record = f"{fund_name}\n{symbol}\n{value_text}"
                    trades[trade_type].append(record)

            total = len(trades["buy"]) + len(trades["sell"])
            if total == 0:
                raise RuntimeError(
                    "جدول بارگذاری شد، اما هیچ ردیفی با نوع معامله «خرید» یا «فروش» پیدا نشد؛ "
                    "برای جلوگیری از ارسال گزارش اشتباه، اجرای ربات متوقف شد."
                )

            logger.info(
                "Extracted %s trade rows (%s buys, %s sells).",
                total, len(trades["buy"]), len(trades["sell"])
            )
            return trades
        finally:
            await browser.close()


async def main():
    trades = await extract_trades()
    now = datetime.now(TEHRAN_TZ).strftime("%Y/%m/%d - %H:%M")
    messages = []

    for trade_type, title, emoji in (
        ("buy", "خریدهای صندوق‌ها", "🟢"),
        ("sell", "فروش‌های صندوق‌ها", "🔴"),
    ):
        records = trades[trade_type]
        if records:
            body = f"{emoji} {title}\n🕒 زمان بررسی: {now} (تهران)\n\n"
            body += "\n\n━━━━━━━━━━━━━━\n\n".join(records)
            messages.extend(split_message(body))

    if not messages:
        raise RuntimeError("گزارشی برای ارسال ساخته نشد.")

    for index, message in enumerate(messages, start=1):
        send_to_telegram(message)
        logger.info("Telegram message %s/%s sent.", index, len(messages))


if __name__ == "__main__":
    asyncio.run(main())
