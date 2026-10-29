import asyncio
from playwright.async_api import async_playwright

URL = "https://app.fundbase.ir/transfers"

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
            print("Table not found. Page might not have loaded correctly.")
        
        content = await page.content()
        print("HTML Length:", len(content))
        
        text = await page.evaluate("document.body.innerText")
        print("Page Text Preview:", text[:1000])
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
