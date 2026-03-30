import requests
import json
import os
import re
from datetime import datetime, timedelta

print("뉴스 수집 시작 (Google News RSS)...")

os.makedirs("data", exist_ok=True)

# ── 카테고리 정의 ─────────────────────────────────────────────────────────
CATEGORIES = {
    "NdFeB": [
        "Nd-Fe-B", "NdFeB", "neodymium", "permanent magnet",
        "sintered magnet", "hot deform", "grain boundary", "coercivity",
        "네오디뮴", "소결자석", "열간변형", "입계확산", "영구자석"
    ],
    "MnBi": [
        "MnBi", "manganese bismuth", "LTP-MnBi",
        "망간비스무스", "망간 비스무트"
    ],
    "NdFeB_Recycling": [
        "recycling", "recycle", "recovery", "HDDR", "urban mining",
        "재활용", "회수", "재생", "수소분쇄"
    ],
}


def classify_category(title, abstract=""):
    """title + abstract 기반으로 카테고리 분류. 매칭 없으면 '기타' 반환"""
    text = (title + " " + abstract).lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "기타"


# ── RSS 피드 목록 ─────────────────────────────────────────────────────────
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=NdFeB+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=neodymium+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=rare+earth+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=MnBi+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=rare+earth+recycling+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=네오디뮴+자석&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=희토류+자석&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=영구자석+희토류&hl=ko&gl=KR&ceid=KR:ko",
]

RELEVANCE_KEYWORDS = [
    "NdFeB", "neodymium", "rare earth", "MnBi", "magnet", "Nd-Fe-B",
    "permanent magnet", "magnet recycling",
    "네오디뮴", "희토류", "영구자석", "자석",
]


def is_relevant(title):
    """관련 키워드 포함 여부 확인"""
    return any(kw.lower() in title.lower() for kw in RELEVANCE_KEYWORDS)


def parse_rss(url):
    """RSS 피드 파싱 → 뉴스 아이템 리스트 반환"""
    try:
        resp = requests.get(
            url, timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RareEarthBot/1.0)"}
        )
        resp.raise_for_status()

        items = re.findall(r'<item>(.*?)</item>', resp.text, re.DOTALL)
        results = []

        for item in items:
            title_m  = re.search(r'<title>(.*?)</title>',       item, re.DOTALL)
            link_m   = re.search(r'<link>(.*?)</link>',         item, re.DOTALL)
            pub_m    = re.search(r'<pubDate>(.*?)</pubDate>',   item, re.DOTALL)
            src_m    = re.search(r'<source[^>]*>(.*?)</source>',item, re.DOTALL)

            if not title_m or not link_m:
                continue

            title = re.sub(r'<[^>]+>', '', title_m.group(1)).strip()
            # CDATA 제거
            title = re.sub(r'<!\[CDATA\[(.*?)\]\]>', r'\1', title).strip()
            link  = link_m.group(1).strip()
            date  = pub_m.group(1).strip()  if pub_m  else ""
            src   = re.sub(r'<[^>]+>', '', src_m.group(1)).strip() if src_m else "Google News"

            results.append({
                "title":  title,
                "url":    link,
                "date":   date,
                "source": src,
            })

        return results

    except Exception as e:
        print(f"  RSS 수집 실패 ({url[:60]}...): {e}")
        return []


def main():
    data_path = "data/news.json"
    today_str = datetime.utcnow().strftime("%Y-%m-%d")
    cutoff    = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

    # ── 기존 뉴스 로드 ────────────────────────────────────────────────────
    existing = {}
    if os.path.exists(data_path):
        try:
            with open(data_path, "r", encoding="utf-8") as f:
                old_list = json.load(f)
            for n in old_list:
                url = n.get("url", "")
                if url:
                    existing[url] = n
            print(f"  기존 뉴스 {len(existing)}건 로드 완료")
        except Exception as e:
            print(f"  기존 데이터 로드 실패 (첫 실행 시 정상): {e}")

    # ── RSS 수집 ──────────────────────────────────────────────────────────
    new_count = 0
    for feed_url in RSS_FEEDS:
        print(f"  피드 수집: {feed_url[feed_url.find('q=')+2:feed_url.find('&')]}")
        items = parse_rss(feed_url)
        for item in items:
            url = item.get("url", "")
            if not url or not is_relevant(item["title"]):
                continue
            if url not in existing:
                item["first_seen"] = today_str
                item["category"]   = classify_category(item["title"])
                existing[url]      = item
                new_count         += 1

    # ── 카테고리 없는 기존 뉴스 보완 ──────────────────────────────────────
    for url, item in existing.items():
        if not item.get("category"):
            item["category"] = classify_category(item.get("title", ""))

    # ── 30일 이내 뉴스만 유지 ─────────────────────────────────────────────
    news_list = [
        n for n in existing.values()
        if n.get("first_seen", "9999-99-99") >= cutoff
    ]
    news_list.sort(key=lambda x: x.get("first_seen", ""), reverse=True)

    # ── 카테고리별 통계 출력 ───────────────────────────────────────────────
    cat_counts = {}
    for n in news_list:
        cat = n.get("category", "기타")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1

    print(f"\n뉴스 수집 완료: {new_count}건 신규 / 총 {len(news_list)}건")
    for cat, cnt in cat_counts.items():
        print(f"  [{cat}] {cnt}건")

    # ── 저장 ──────────────────────────────────────────────────────────────
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=2)

    print(f"data/news.json 저장 완료!")


if __name__ == "__main__":
    main()
