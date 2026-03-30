code = '''import requests
import json
import os
import re
from datetime import datetime, timedelta

print("뉴스 수집 시작 (Google News RSS + 네이버 뉴스 RSS)...")

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
        "망간비스무스", "망간 비스무트", "망간비스무트", "비스무트"
    ],
    "NdFeB_Recycling": [
        "recycling", "recycle", "recovery", "hydrogen decrepitation", "urban mining",
        "재활용", "회수", "재생", "수소분쇄"
    ],
}


def classify_category(title, abstract=""):
    """title + abstract 기반으로 카테고리 분류"""
    text = (title + " " + abstract).lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "기타"


# ── RSS 피드 (영문: Google / 한국어: 네이버) ──────────────────────────────
ENGLISH_FEEDS = [
    "https://news.google.com/rss/search?q=NdFeB+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=neodymium+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=rare+earth+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=MnBi+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=rare+earth+recycling+magnet&hl=en&gl=US&ceid=US:en",
]

KOREAN_FEEDS = [
    "https://news.naver.com/search/rss?query=네오디뮴+자석",
    "https://news.naver.com/search/rss?query=희토류+자석",
    "https://news.naver.com/search/rss?query=영구자석+희토류",
    "https://news.naver.com/search/rss?query=망간비스무트+자석",
    "https://news.naver.com/search/rss?query=희토류+재활용",
]

EN_KEYWORDS = [
    "NdFeB", "neodymium", "rare earth", "MnBi", "magnet", "Nd-Fe-B",
    "permanent magnet", "magnet recycling",
]
KO_KEYWORDS = [
    "네오디뮴", "희토류", "영구자석", "자석", "망간비스무트",
    "망간비스무스", "비스무트", "재활용",
]


def is_relevant(title, lang):
    """언어별 관련 키워드 포함 여부 확인"""
    keywords = KO_KEYWORDS if lang == "ko" else EN_KEYWORDS
    return any(kw.lower() in title.lower() for kw in keywords)


def has_korean(text):
    """한글 포함 여부로 언어 감지"""
    return bool(re.search(r"[가-힣]", text))


def parse_rss(url):
    """RSS 피드 파싱 → 뉴스 아이템 리스트 반환"""
    try:
        resp = requests.get(
            url, timeout=10,
            headers={"User-Agent": "Mozilla/5.0 (compatible; RareEarthBot/1.0)"}
        )
        resp.raise_for_status()

        items = re.findall(r"<item>(.*?)</item>", resp.text, re.DOTALL)
        results = []

        for item in items:
            title_m = re.search(r"<title>(.*?)</title>",         item, re.DOTALL)
            link_m  = re.search(r"<link>(.*?)</link>",           item, re.DOTALL)
            pub_m   = re.search(r"<pubDate>(.*?)</pubDate>",     item, re.DOTALL)
            src_m   = re.search(r"<source[^>]*>(.*?)</source>",  item, re.DOTALL)

            if not title_m or not link_m:
                continue

            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
            title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title).strip()
            link  = link_m.group(1).strip()
            date  = pub_m.group(1).strip() if pub_m else ""
            src   = re.sub(r"<[^>]+>", "", src_m.group(1)).strip() if src_m else ""

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
                    # source_lang 없는 기존 데이터 보완
                    if not n.get("source_lang"):
                        n["source_lang"] = "ko" if has_korean(n.get("title", "")) else "en"
                    existing[url] = n
            print(f"  기존 뉴스 {len(existing)}건 로드 완료")
        except Exception as e:
            print(f"  기존 데이터 로드 실패 (첫 실행 시 정상): {e}")

    # ── 영문 뉴스 수집 (Google News) ─────────────────────────────────────
    new_en = 0
    print("\\n  [영문] Google News RSS 수집 중...")
    for feed_url in ENGLISH_FEEDS:
        kw = feed_url[feed_url.find("q=")+2 : feed_url.find("&")]
        print(f"    피드: {kw}")
        for item in parse_rss(feed_url):
            url = item.get("url", "")
            if not url or not is_relevant(item["title"], "en"):
                continue
            if url not in existing:
                item["first_seen"]  = today_str
                item["source_lang"] = "en"
                item["category"]    = classify_category(item["title"])
                if not item["source"]:
                    item["source"] = "Google News"
                existing[url] = item
                new_en += 1

    # ── 한국어 뉴스 수집 (네이버 뉴스) ──────────────────────────────────
    new_ko = 0
    print("\\n  [국내] 네이버 뉴스 RSS 수집 중...")
    for feed_url in KOREAN_FEEDS:
        kw = feed_url[feed_url.find("query=")+6:]
        print(f"    피드: {kw}")
        for item in parse_rss(feed_url):
            url = item.get("url", "")
            if not url or not is_relevant(item["title"], "ko"):
                continue
            if url not in existing:
                item["first_seen"]  = today_str
                item["source_lang"] = "ko"
                item["category"]    = classify_category(item["title"])
                if not item["source"]:
                    item["source"] = "네이버 뉴스"
                existing[url] = item
                new_ko += 1

    # ── 카테고리 없는 기존 뉴스 보완 ─────────────────────────────────────
    for item in existing.values():
        if not item.get("category"):
            item["category"] = classify_category(item.get("title", ""))

    # ── 30일 이내 뉴스만 유지 ─────────────────────────────────────────────
    news_list = [
        n for n in existing.values()
        if n.get("first_seen", "9999-99-99") >= cutoff
    ]
    news_list.sort(key=lambda x: x.get("first_seen", ""), reverse=True)

    # ── 통계 출력 ──────────────────────────────────────────────────────────
    ko_total = sum(1 for n in news_list if n.get("source_lang") == "ko")
    en_total = sum(1 for n in news_list if n.get("source_lang") == "en")
    print(f"\\n뉴스 수집 완료:")
    print(f"  신규 → 해외 {new_en}건 / 국내 {new_ko}건")
    print(f"  전체 → 해외 {en_total}건 / 국내 {ko_total}건 / 합계 {len(news_list)}건")

    cat_counts = {}
    for n in news_list:
        cat = n.get("category", "기타")
        cat_counts[cat] = cat_counts.get(cat, 0) + 1
    for cat, cnt in cat_counts.items():
        print(f"  [{cat}] {cnt}건")

    # ── 저장 ──────────────────────────────────────────────────────────────
    with open(data_path, "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=2)

    print("data/news.json 저장 완료!")


if __name__ == "__main__":
    main()
'''

with open('fetch_news.py', 'w', encoding='utf-8') as f:
    f.write(code)

print("fetch_news.py 생성 완료!")
print()
print("=== 변경 사항 ===")
print("영문: Google News RSS 5개  → source_lang = 'en'")
print("국내: 네이버 뉴스 RSS 5개  → source_lang = 'ko'")
print()
print("=== 국내 RSS 피드 ===")
feeds = [
    "네오디뮴+자석",
    "희토류+자석",
    "영구자석+희토류",
    "망간비스무트+자석",
    "희토류+재활용",
]
for f in feeds:
    print(f"  https://news.naver.com/search/rss?query={f}")

