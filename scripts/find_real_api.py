import requests
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

url = "https://cdn.104.com.tw/cindex/jobs/index/remote/search/assets/__federation_expose_Search-efCY_5Ey.js"
code = requests.get(url).text

# Find where search request is constructed
for m in re.finditer(r'(/jobs/search/[a-zA-Z0-9_/]+)', code):
    print("Search path in JS:", m.group(1))

# Find axios baseURL or api baseURL
for m in re.finditer(r'(baseURL|baseUrl)\s*:\s*["\']([^"\']+)["\']', code):
    print("Base URL in JS:", m.group(1), m.group(2))

# Find any string containing "list"
for m in re.finditer(r'["\']([^"\']*jobs/search/list[^"\']*)["\']', code):
    print("Match jobs/search/list:", m.group(1))
