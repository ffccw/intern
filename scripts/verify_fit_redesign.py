import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page(viewport={"width": 1280, "height": 950})
        
        errors = []
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        
        print("Navigating to http://localhost:3000...")
        await page.goto("http://localhost:3000")
        await page.wait_for_timeout(1000)
        
        # 1. Open Fit Modal in Macro (All Jobs)
        print("Opening Fit Modal (All jobs)...")
        await page.click("#btn-fit-quick")
        await page.wait_for_timeout(500)
        
        # Click Data preset (商業數據型)
        print("Selecting Data preset...")
        await page.click("button[data-preset='data']")
        await page.wait_for_timeout(500)
        
        modal_path = "C:/Users/User/.gemini/antigravity/brain/d1ab4c62-251f-4279-aca7-e376011dd061/fit_modal_macro.png"
        await page.screenshot(path=modal_path)
        print("Saved Macro Fit Modal screenshot to:", modal_path)
        
        # 2. Apply Fit
        print("Applying Fit Ranking...")
        await page.click("#btn-apply-fit-modal")
        await page.wait_for_timeout(800)
        
        # 3. Expand first job card to see micro breakdown
        print("Expanding top-matched job card...")
        first_expand = await page.query_selector(".btn-toggle-detail")
        if first_expand:
            await first_expand.click()
            await page.wait_for_timeout(500)
            
        card_path = "C:/Users/User/.gemini/antigravity/brain/d1ab4c62-251f-4279-aca7-e376011dd061/job_card_micro_fit.png"
        await page.screenshot(path=card_path)
        print("Saved Job Card Micro Fit screenshot to:", card_path)
        
        # 4. Test Domain Filtering Linkage
        print("Switching filter to '商業數據分析'...")
        data_domain_btn = await page.query_selector("button.filter-btn[data-val='數據分析']")
        if data_domain_btn:
            await data_domain_btn.click()
            await page.wait_for_timeout(500)
            
        # Re-open modal to observe domain-linked gap analysis
        print("Opening modal in Data Analytics domain context...")
        await page.click("#btn-fit-quick")
        await page.wait_for_timeout(500)
        
        modal_domain_path = "C:/Users/User/.gemini/antigravity/brain/d1ab4c62-251f-4279-aca7-e376011dd061/fit_modal_domain_linked.png"
        await page.screenshot(path=modal_domain_path)
        print("Saved Domain-Linked Fit Modal screenshot to:", modal_domain_path)
        
        await page.click("#btn-close-fit")
        await page.wait_for_timeout(300)
        
        # 5. Switch to English
        print("Switching to English...")
        await page.click("#lang-toggle")
        await page.wait_for_timeout(500)
        
        # Expand card in English to inspect micro match
        first_expand_en = await page.query_selector(".btn-toggle-detail")
        if first_expand_en:
            await first_expand_en.click()
            await page.wait_for_timeout(500)
            
        card_en_path = "C:/Users/User/.gemini/antigravity/brain/d1ab4c62-251f-4279-aca7-e376011dd061/job_card_micro_fit_en.png"
        await page.screenshot(path=card_en_path)
        print("Saved English Card Micro Fit screenshot to:", card_en_path)
        
        print("Console errors:", errors)
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
