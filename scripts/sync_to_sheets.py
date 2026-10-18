import json
import requests
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_FILE = BASE_DIR / "data" / "data.json"

WEBHOOK_URL = "https://script.google.com/macros/s/AKfycbwnzrqJFhIxjaJKWjrftSnRM_6TNzxmKGuBjEKSkh2Br52Ywc0i2FPSDDSUeBlj9vLe/exec"

def sync():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    
    jobs = data.get("jobs", [])
    print(f"Sending {len(jobs)} jobs to Google Apps Script...")
    
    # Google Apps Script handles JSON payloads
    resp = requests.post(
        WEBHOOK_URL,
        data=json.dumps(jobs, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        allow_redirects=True,
        timeout=30
    )
    
    print("HTTP Status Code:", resp.status_code)
    print("Response text:", resp.text)
    if resp.status_code == 200 and "success" in resp.text:
        print("SUCCESS! Data successfully written to Google Sheet!")
    else:
        print("Warning: Response was not success, checking details...")

if __name__ == "__main__":
    sync()
