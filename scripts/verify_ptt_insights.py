import asyncio
from playwright.async_api import async_playwright

async def run():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 960})

        # 1. Open home page
        await page.goto("http://localhost:3000", wait_until="networkidle")
        await page.wait_for_selector(".job-card")

        # 2. Capture Header & Job Cards with PTT button in Chinese mode
        await page.screenshot(path="ptt_button_cards_zh.png")
        print("Captured ptt_button_cards_zh.png")

        # 3. Click English toggle
        await page.click("#lang-toggle")
        await page.wait_for_timeout(500)
        await page.screenshot(path="ptt_button_cards_en.png")
        print("Captured ptt_button_cards_en.png")

        # 4. Click Insights tab in English mode
        await page.click("#nav-insights")
        await page.wait_for_timeout(600)
        await page.screenshot(path="insights_english_full.png")
        print("Captured insights_english_full.png")

        # 5. Click Chinese toggle while in Insights
        await page.click("#lang-toggle")
        await page.wait_for_timeout(600)
        await page.screenshot(path="insights_chinese_full.png")
        print("Captured insights_chinese_full.png")

        # 6. Check PTT button count
        ptt_buttons = await page.query_selector_all(".btn-ptt-eval")
        print(f"Total PTT buttons rendered: {len(ptt_buttons)}")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run())
