import arxiv, json
from datetime import datetime

client = arxiv.Client()
search = arxiv.Search(
    query="(NdFeB OR Nd-Fe-B OR rare earth magnet OR neodymium OR Ce substitution magnet)",
    max_results=10,
    sort_by=arxiv.SortCriterion.SubmittedDate
)

papers = []
for r in client.results(search):
    papers.append({
        "title": r.title,
        "authors": ", ".join([a.name for a in r.authors[:3]]),
        "abstract": r.summary[:200] + "...",
        "url": r.entry_id,
        "date": r.published.strftime("%Y-%m-%d")
    })

with open("data/papers.json", "w", encoding="utf-8") as f:
    json.dump({"updated": datetime.now().strftime("%Y-%m-%d"), "items": papers}, f, ensure_ascii=False, indent=2)
print(f"✅ 논문 {len(papers)}건 저장")
