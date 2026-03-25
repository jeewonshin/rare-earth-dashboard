import requests
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

print("📡 논문 수집 시작 (arXiv + CrossRef)...")

os.makedirs("data", exist_ok=True)

# ── 키워드 구조 ───────────────────────────────────────────
# 필수: permanent magnet OR Nd-Fe-B
# 세부: Hot deform OR Ce substituted OR Grain boundary diffusion

ARXIV_QUERY = (
    '(ti:"permanent magnet" OR ti:"Nd-Fe-B" OR abs:"permanent magnet" OR abs:"Nd-Fe-B")'
    ' AND '
    '(ti:"Hot deform" OR ti:"Ce substituted" OR ti:"Grain boundary diffusion"'
    ' OR abs:"Hot deform" OR abs:"Ce substituted" OR abs:"Grain boundary diffusion")'
)

CROSSREF_QUERY = '"permanent magnet" "Nd-Fe-B" "Hot deform" OR "Ce substituted" OR "Grain boundary diffusion"'

# 필터링용 (CrossRef 결과 후처리)
MUST_KEYWORDS   = ["permanent magnet", "nd-fe-b", "ndfeb"]
DETAIL_KEYWORDS = ["hot deform", "ce substitut", "grain boundary diffusion"]

papers      = []
seen_titles = set()


# ================================================
# 1. arXiv API
# ================================================
print("\n  [1/2] arXiv 수집 중...")

try:
    res = requests.get(
        "https://export.arxiv.org/api/query",
        params={
            "search_query": ARXIV_QUERY,
            "start":        0,
            "max_results":  10,
            "sortBy":       "submittedDate",
            "sortOrder":    "descending",
        },
        timeout=20
    )

    ns   = {"atom": "http://www.w3.org/2005/Atom"}
    root = ET.fromstring(res.text)

    for entry in root.findall("atom:entry", ns):
        title    = entry.find("atom:title",     ns).text.strip().replace("\n", " ")
        url      = entry.find("atom:id",        ns).text.strip()
        date_raw = entry.find("atom:published", ns).text.strip()[:10]
        authors  = [a.find("atom:name", ns).text
                    for a in entry.findall("atom:author", ns)]
        abstract = entry.find("atom:summary",   ns).text.strip().replace("\n", " ")

        # 후처리 필터링
        text_lower = (title + " " + abstract).lower()
        has_must   = any(k in text_lower for k in MUST_KEYWORDS)
        has_detail = any(k in text_lower for k in DETAIL_KEYWORDS)

        if not (has_must and has_detail):
            continue

        if title not in seen_titles:
            seen_titles.add(title)
            papers.append({
                "title":    title,
                "authors":  ", ".join(authors[:3]) + (" et al." if len(authors) > 3 else ""),
                "date":     date_raw,
                "url":      url,
                "abstract": abstract[:200] + "...",
                "source":   "arXiv",
            })

    print(f"  ✅ arXiv {len(papers)}건 수집")

except Exception as e:
    print(f"  ❌ arXiv 실패: {e}")


# ================================================
# 2. CrossRef API
# ================================================
print("\n  [2/2] CrossRef 수집 중...")

crossref_count = 0

try:
    from_date = (datetime.now() - timedelta(days=180)).strftime("%Y-%m-%d")

    res = requests.get(
        "https://api.crossref.org/works",
        params={
            "query":  CROSSREF_QUERY,
            "filter": f"from-pub-date:{from_date},type:journal-article",
            "rows":   20,
            "sort":   "published",
            "order":  "desc",
            "select": "title,author,published,URL,abstract,container-title",
        },
        headers={"User-Agent": "RareEarthDashboard/1.0 (research tool)"},
        timeout=20
    )

    items = res.json().get("message", {}).get("items", [])

    for item in items:
        title_list = item.get("title", [])
        if not title_list:
            continue
        title = title_list[0].strip()
        if title in seen_titles:
            continue

        abstract_raw   = item.get("abstract", "")
        abstract_clean = re.sub(r"<[^>]+>", "", abstract_raw)

        # 후처리 필터링
        text_lower = (title + " " + abstract_clean).lower()
        has_must   = any(k in text_lower for k in MUST_KEYWORDS)
        has_detail = any(k in text_lower for k in DETAIL_KEYWORDS)

        if not (has_must and has_detail):
            continue

        authors_raw = item.get("author", [])
        authors_str = ", ".join(
            f"{a.get('given','')} {a.get('family','')}".strip()
            for a in authors_raw[:3]
        ) + (" et al." if len(authors_raw) > 3 else "")

        pub      = item.get("published", {}).get("date-parts", [[""]])[0]
        date_str = "-".join(str(x).zfill(2) for x in pub if x) or ""
        journal  = item.get("container-title", [""])[0]
        url      = item.get("URL", "#")

        seen_titles.add(title)
        papers.append({
            "title":    title,
            "authors":  authors_str,
            "date":     date_str,
            "url":      url,
            "abstract": abstract_clean[:200] + "...",
            "source":   f"CrossRef ({journal})" if journal else "CrossRef",
        })
        crossref_count += 1

    print(f"  ✅ CrossRef {crossref_count}건 수집")

except Exception as e:
    print(f"  ❌ CrossRef 실패: {e}")


# ── 날짜 기준 최신순 정렬 ─────────────────────────────────
papers.sort(key=lambda x: x["date"], reverse=True)
papers = papers[:15]

# ── 논문 발행일 기준 7일 이내면 NEW ──────────────────────
today = datetime.now().date()

for p in papers:
    try:
        pub_date    = datetime.strptime(p["date"][:10], "%Y-%m-%d").date()
        p["is_new"] = (today - pub_date).days <= 7
    except:
        p["is_new"] = False

new_count = sum(1 for p in papers if p["is_new"])
print(f"\n신규 논문 (7일 이내): {new_count}건 / 전체: {len(papers)}건")

output = {
    "updated":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    "source":    "arXiv + CrossRef",
    "new_count": new_count,
    "items":     papers,
}

with open("data/papers.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\n✅ data/papers.json 저장 완료!")
