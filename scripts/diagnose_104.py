import requests
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

url = "https://www.104.com.tw/jobs/search/list"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://www.104.com.tw/jobs/search/?keyword=%E5%AF%A6%E7%BF%92&order=1&jobsource=2018indexpoc&ro=0",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}
params = {
    "keyword": "實習",
    "page": 1,
    "ro": 0,
    "order": 1,
    "asc": 0,
    "mode": "s",
    "jobsource": "2018indexpoc"
}

r = requests.get(url, headers=headers, params=params)
print("Status:", r.status_code)
print("Content-type:", r.headers.get("content-type"))
try:
    data = r.json()
    jobs = data.get("data", {}).get("list", [])
    print(f"SUCCESS! Retrieved {len(jobs)} jobs via JSON!")
    for j in jobs[:5]:
        print("-", j.get("custName"), "|", j.get("jobName"), "| ID:", j.get("jobNo"), "| Link:", j.get("link", {}).get("job"))
except Exception as e:
    print("Failed to parse JSON:", e)
    print("First 200 chars:", r.text[:200])
