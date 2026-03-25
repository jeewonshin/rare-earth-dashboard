# ── 논문 발행일 기준 7일 이내면 NEW ──────────────────────
today = datetime.now().date()

for p in papers:
    try:
        pub_date   = datetime.strptime(p["date"][:10], "%Y-%m-%d").date()
        p["is_new"] = (today - pub_date).days <= 7
    except:
        p["is_new"] = False

new_count = sum(1 for p in papers if p["is_new"])
print(f"신규 논문 (7일 이내): {new_count}건 / 전체: {len(papers)}건")

output = {
    "updated":   datetime.now().strftime("%Y-%m-%d %H:%M"),
    "source":    "arXiv + CrossRef",
    "new_count": new_count,
    "items":     papers,
}

with open("data/papers.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\n✅ data/papers.json 저장 완료!")
