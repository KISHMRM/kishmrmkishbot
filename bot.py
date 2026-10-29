import asyncio
from playwright.async_api import async_playwright

URL = "https://app.fundbase.ir/transfers"

async def main():
    print("Starting Playwright...")
    async with async_playwright() as p:
        # اجرای مرورگر در حالت Headless (بدون نمایش پنجره)
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        
        print(f"Going to {URL}")
        # رفتن به صفحه و صبر کردن تا شبکه آرام بشه
        await page.goto(URL, wait_until="networkidle", timeout=60000)
        
        # صبر میکنیم تا جدول لود بشه (این سلکتور ممکنه نیاز به تغییر داشته باشه)
        # منتظر می‌مونیم تا تگ table در صفحه ظاهر بشه
        try:
            await page.wait_for_selector("table", timeout=15000)
            print("Table found!")
        except Exception:
            print("Table not found. Page might not have loaded correctly.")
        
        # استخراج کل متن صفحه برای تست
        content = await page.content()
        print("HTML Length:", len(content))
        
        # گرفتن متن جدول (اگر جدول پیدا شد)
        # این بخش رو بعدا دقیق‌تر می‌کنیم
        text = await page.evaluate("document.body.innerText")
        print("Page Text Preview:", text[:1000])
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
