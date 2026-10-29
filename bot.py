
import os
import hashlib
import requests
from bs4 import BeautifulSoup

PAGE_URL = os.environ["PAGE_URL"]
BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]
CSS_SELECTOR = os.environ["CSS_SELECTOR"]


def main():
    response = requests.get(
        PAGE_URL,
        timeout=30,
        headers={"User-Agent": "Mozilla/5.0"}
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    elements = soup.select(CSS_SELECTOR)

    if not elements:
        raise RuntimeError(
            "No matching content found. Check the page selector."
        )

    content = "\n\n".join(
        element.get_text(" ", strip=True)
        for element in elements
    ).strip()

    if not content:
        raise RuntimeError("The selected content is empty.")

    digest = hashlib.sha256(
        content.encode("utf-8")
    ).hexdigest()

    # فعلاً فقط استخراج را آزمایش می‌کنیم.
    print("Page fetched successfully.")
    print("Content length:", len(content))
    print("Content fingerprint:", digest)
    print("Preview:", content[:500])

    # ارسال پیام را بعد از تنظیم صفحه و
    # روش ذخیره وضعیت تغییرات فعال می‌کنیم.


if __name__ == "__main__":
    main()
