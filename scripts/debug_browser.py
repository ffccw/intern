import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 900})

        page.on("console", lambda msg: print(f"[Browser Console] {msg.type}: {msg.text}"))
        page.on("pageerror", lambda err: print(f"[Browser PageError] {err}"))

        await page.goto("http://localhost:3000")
        await page.wait_for_timeout(3000)

        html = await page.content()
        print("Page title:", await page.title())
        cards = await page.query_selector_all(".job-card")
        print("Job cards found:", len(cards))

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
