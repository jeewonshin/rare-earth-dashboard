import requests, json, os
from datetime import datetime

API_KEY = os.environ.get("SERP_API_KEY", "")
params = {
    "engine": "google_patents",
    "q": "NdFeB rare earth magnet Ce substitution",
    "sort": "new",
    "api_key": API_KEY
}

patents = []
try:
    res = requests.get("https://serpapi.com/search", params=params, timeout=15)
    data = res.json()
    for p in data.get("organic_results", [])[:10]:
        patents.append({
            "title": p.get("title", "제목 없음"),
            "assignee": p.get("assignee", "출원인 미상"),
            "date": p.get("filing_date", ""),
            "url": p.get("patent_link", "#"),
            "snippet": p.get("snippet", "")[:150]
        })
except Exception as e:
    print(f"⚠️ 특허 수집 오류: {e}")

with open("data/patents.json", "w", encoding="utf-8") as f:
    json.dump({"updated": datetime.now().strftime("%Y-%m-%d"), "items": patents}, f, ensure_ascii=False, indent=2)
print(f"✅ 특허 {len(patents)}건 저장")
