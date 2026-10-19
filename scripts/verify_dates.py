from playwright.sync_api import sync_playwright
import time
from pathlib import Path

ARTIFACT_DIR = Path(r"C:\Users\User\.gemini\antigravity\brain\d1ab4c62-251f-4279-aca7-e376011dd061")
SCREENSHOT_DATES = ARTIFACT_DIR / "dates_verified_preview.png"

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page(viewport={"width": 1280, "height": 950})
    page.goto("http://localhost:3000", wait_until="networkidle")
    
    # 1. Enforce dark mode
    page.evaluate("document.documentElement.classList.add('dark'); localStorage.setItem('tw50_theme', 'dark'); localStorage.setItem('tw50_lang', 'zh');")
    page.reload(wait_until="networkidle")
    time.sleep(0.5)
    
    # Take screenshot showing first 2-3 cards with real dates
    page.screenshot(path=str(SCREENSHOT_DATES))
    print(f"Saved verified dates screenshot to {SCREENSHOT_DATES}")
    browser.close()
