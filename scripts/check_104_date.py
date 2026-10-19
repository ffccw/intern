from playwright.sync_api import sync_playwright
import json

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
        if "jobs/search/api/jobs" in res.url and res.status == 200:
            try:
                payload = res.json()
                d = payload.get("data")
                items = []
                if isinstance(d, dict):
                    items = d.get("list", [])
                elif isinstance(d, list):
                    items = d
                if items:
                    print("Found items count:", len(items))
                    item = items[0]
                    print("Sample item keys:", sorted(list(item.keys())))
                    for k in sorted(list(item.keys())):
                        if any(x in k.lower() for x in ["date", "time", "day", "appear"]):
                            print(f"Date Key -> {k}: {item[k]}")
            except Exception as e:
                print("Error parsing json:", e)
                
    page.on("response", handle_resp)
    page.goto("https://www.104.com.tw/jobs/search/?keyword=%E5%AF%8C%E9%82%A6%E9%87%91%20%E5%AF%A6%E7%BF%92", wait_until="domcontentloaded")
    page.wait_for_timeout(4000)
    browser.close()
