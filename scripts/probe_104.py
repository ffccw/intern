"""
極簡 104 真實資料探測腳本 (Spike Probe)
只抓 2 筆職缺，觀察 104 真實回傳結構與欄位名稱。
"""
import urllib.request
import json
import ssl

# 104 搜尋 API (使用 jobcat 產品企劃/專案管理類別: 2007001000)
# 依照 PRD 規定：不帶 keyword 參數
url = (
    "https://www.104.com.tw/jobs/search/list?"
    "ro=0&jobcat=2007001000&order=15&asc=0&page=1&mode=s&jobsource=2018indexpoc"
)

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.104.com.tw/jobs/search/",
}

req = urllib.request.Request(url, headers=headers)
context = ssl._create_unverified_context()

try:
    with urllib.request.urlopen(req, context=context, timeout=10) as response:
        data = json.loads(response.read().decode("utf-8"))
        job_list = data.get("data", {}).get("list", [])
        
        print(f"成功連線 104！本頁總共找到 {len(job_list)} 筆職缺。\n")
        print("=== 挑選前 2 筆真實職缺的原始欄位 ===")
        
        for i, job in enumerate(job_list[:2], 1):
            print(f"\n【職缺 {i}】")
            print(f"  職缺代碼 (jobNo / job_id): {job.get('jobNo')}")
            print(f"  職稱 (jobName): {job.get('jobName')}")
            print(f"  公司名稱 (custName): {job.get('custName')}")
            print(f"  工作地區 (jobAddrNoDesc): {job.get('jobAddrNoDesc')}")
            print(f"  薪資待遇 (salaryDesc): {job.get('salaryDesc')}")
            print(f"  經歷要求 (periodDesc): {job.get('periodDesc')}")
            print(f"  學歷要求 (optionEdu): {job.get('optionEdu')}")
            print(f"  職缺連結: https:{job.get('link', {}).get('job')}")
            print(f"  原始簡介摘要: {job.get('description', '')[:60]}...")

except Exception as e:
    print(f"連線或解析失敗: {e}")
