from playwright.sync_api import sync_playwright
import time
from pathlib import Path

ARTIFACT_DIR = Path(r"C:\Users\User\.gemini\antigravity\brain\d1ab4c62-251f-4279-aca7-e376011dd061")
SCREENSHOT_EXPANDED = ARTIFACT_DIR / "expanded_card_preview.png"
SCREENSHOT_EN = ARTIFACT_DIR / "english_view_preview.png"
SCREENSHOT_INSIGHTS = ARTIFACT_DIR / "insights_view_preview.png"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 950})
    page.goto("http://localhost:3000", wait_until="networkidle")
    
    # 1. Enforce dark mode
    page.evaluate("document.documentElement.classList.add('dark'); localStorage.setItem('tw50_theme', 'dark');")
    time.sleep(0.5)
    
    # 2. Click the first Expand Button
    expand_btn = page.query_selector(".btn-toggle-detail")
    if expand_btn:
        expand_btn.click()
        time.sleep(0.5)
        print("Clicked expand button successfully!")
    else:
        print("Error: expand button not found!")
        
    page.screenshot(path=str(SCREENSHOT_EXPANDED))
    print(f"Saved expanded screenshot to {SCREENSHOT_EXPANDED}")
    
    # 3. Test Language Switcher to EN
    lang_btn = page.query_selector("#lang-toggle")
    if lang_btn:
        lang_btn.click()
        time.sleep(0.5)
        print("Toggled language to EN successfully!")
        page.screenshot(path=str(SCREENSHOT_EN))
        print(f"Saved EN screenshot to {SCREENSHOT_EN}")
        
    # 4. Test Insights Navigation
    insights_btn = page.query_selector("#nav-insights")
    if insights_btn:
        insights_btn.click()
        time.sleep(0.5)
        print("Switched to Insights tab successfully!")
        page.screenshot(path=str(SCREENSHOT_INSIGHTS))
        print(f"Saved Insights screenshot to {SCREENSHOT_INSIGHTS}")
        
    browser.close()
