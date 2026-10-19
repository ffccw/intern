from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(
        channel="chrome",
        headless=False,
        args=["--disable-blink-features=AutomationControlled", "--no-sandbox"]
    )
    context = browser.new_context(
        user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        viewport={"width": 1280, "height": 800},
        locale="zh-TW"
    )
    page = context.new_page()
    page.add_init_script("Object.defineProperty(navigator, 'webdriver', { get: () => undefined });")
    
    def handle_resp(res):
        if "ajax/content" in res.url or "job" in res.url:
            if "json" in res.headers.get("content-type", ""):
                print("JSON response from:", res.url)
                try:
                    data = res.json()
                    header = data.get("data", {}).get("header", {})
                    if header:
                        print("Header keys:", list(header.keys()))
                        print("appearDate in header:", header.get("appearDate"))
                except Exception as e:
                    pass
                    
    page.on("response", handle_resp)
    page.goto("https://www.104.com.tw/job/8r5sb", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    
    # Also get visible text containing 更新
    body_text = page.inner_text("body")
    lines = [l.strip() for l in body_text.split("\n") if "更新" in l or "2026" in l or "10/" in l]
    print("Visible lines with 更新 or 2026 or 10/:", lines[:10])
    
    browser.close()
