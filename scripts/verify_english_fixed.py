from playwright.sync_api import sync_playwright
import time
from pathlib import Path

ARTIFACT_DIR = Path(r"C:\Users\User\.gemini\antigravity\brain\d1ab4c62-251f-4279-aca7-e376011dd061")
SCREENSHOT_EN_FIXED = ARTIFACT_DIR / "english_fixed_preview.png"
SCREENSHOT_YUANTA = ARTIFACT_DIR / "english_yuanta_preview.png"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 950})
    page.goto("http://localhost:3000", wait_until="networkidle")
    
    # 1. Enforce English and Dark Mode
    page.evaluate("document.documentElement.classList.add('dark'); localStorage.setItem('tw50_theme', 'dark'); localStorage.setItem('tw50_lang', 'en');")
    page.reload(wait_until="networkidle")
    time.sleep(1.0)
    
    # Take screenshot of top English view
    page.screenshot(path=str(SCREENSHOT_EN_FIXED))
    print(f"Saved EN fixed screenshot to {SCREENSHOT_EN_FIXED}")
    
    # Search for Yuanta to inspect the exact card from the user's screenshot
    search_input = page.query_selector("#search-input")
    if search_input:
        search_input.fill("Yuanta")
        time.sleep(0.5)
        
    page.screenshot(path=str(SCREENSHOT_YUANTA))
    print(f"Saved Yuanta EN screenshot to {SCREENSHOT_YUANTA}")
    
    browser.close()
