import json

with open("data/data.json", "r", encoding="utf-8") as f:
    data = json.load(f)

jobs = data.get("jobs", [])
print(f"Total jobs: {len(jobs)}")

# Check 1: Boilerplate presence
bp = "參與專案日常進度追蹤與時程控管"
bp_count = sum(1 for j in jobs if bp in j.get("job_duties", []))
print(f"Jobs with old boilerplate duties: {bp_count} (Must be 0)")

# Check 2: Job 4 (廣明光電)
j4 = next(j for j in jobs if "影像標記" in j.get("title", ""))
print("\n=== Job 4 Verification ===")
print("Company:", j4["company"])
print("Salary:", j4["salary_desc"])
print("Duties:", j4["job_duties"])
print("Courses:", j4["recommended_courses"])
print("Collaborators:", j4["collaborators"])

# Check 3: Mismatched HR courses on tech jobs
mismatches = [
    j["title"] for j in jobs
    if any(k in j["title"] for k in ["AI", "軟體", "工程", "IT", "Java", "SMT", "C#"])
    and any(c in j.get("recommended_courses", []) for c in ["人力資源管理", "組織行為學"])
]
print(f"\nTech jobs with mismatched HR courses: {len(mismatches)} (Must be 0)")

# Check 4: Diversity of duties
duties_samples = [j["job_duties"][0] for j in jobs[:8]]
print("\n=== First 8 Jobs Duty 1 Samples ===")
for i, d in enumerate(duties_samples):
    print(f"Job {i}: {d}")
