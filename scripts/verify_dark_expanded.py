import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 960})

        await page.goto("http://localhost:3000", wait_until="networkidle")
        await page.wait_for_selector(".job-card")

        # Toggle Dark Mode
        await page.click("#theme-toggle")
        await page.wait_for_timeout(400)

        # Expand first card
        first_expand = await page.query_selector(".btn-toggle-detail")
        if first_expand:
            await first_expand.click()
            await page.wait_for_timeout(400)

        await page.screenshot(path="ptt_dark_mode_expanded.png")
        print("Captured ptt_dark_mode_expanded.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
