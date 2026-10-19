import json

with open("data/data.json", encoding="utf-8") as f:
    data = json.load(f)

ptt_jobs = [j for j in data["jobs"] if j.get("discussion_links", {}).get("ptt_url")]
print(f"Total jobs with PTT link: {len(ptt_jobs)} / {len(data['jobs'])}")

companies = {}
for j in ptt_jobs:
    comp = f"{j['company']} ({j['stock_code']})"
    if comp not in companies:
        companies[comp] = []
    companies[comp].append((j["title"], j["discussion_links"]["ptt_url"]))

print("\n--- Summary by Company ---")
for comp, jobs in sorted(companies.items(), key=lambda x: len(x[1]), reverse=True):
    print(f"\n[{comp}] ({len(jobs)} 筆職缺):")
    for title, url in jobs:
        print(f"  * {title}")
        print(f"    PTT: {url}")
