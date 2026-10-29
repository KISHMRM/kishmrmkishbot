
import requests
from bs4 import BeautifulSoup

URL = "https://app.fundbase.ir/transfers"

def main():
    print("Checking Fundbase transfers page...")

    response = requests.get(
        URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )

    print("HTTP status:", response.status_code)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    print("Page title:", soup.title.get_text(strip=True) if soup.title else "No title")
    print("HTML length:", len(response.text))
    print("Visible text preview:")
    print(soup.get_text(" ", strip=True)[:2500])

    if len(soup.get_text(strip=True)) < 100:
        print("WARNING: Very little text found; JavaScript may be required.")

if __name__ == "__main__":
    main()
