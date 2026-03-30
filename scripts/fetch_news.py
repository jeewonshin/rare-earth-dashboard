import requests
import json
import os
import re
from datetime import datetime, timedelta

print("뉴스 수집 시작 (Google News RSS - 영문 + 한국어)...")

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


def detect_lang(title):
    """제목에 한글 포함 여부로 언어 판단"""
    return "ko" if re.search(r"[가-힣]", title) else "en"


# ── RSS 피드 (구글 뉴스 - 영문 + 한국어 키워드) ───────────────────────────
RSS_FEEDS = [
    # 영문 검색
    "https://news.google.com/rss/search?q=NdFeB+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=neodymium+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=rare+earth+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=MnBi+magnet&hl=en&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=rare+earth+recycling+magnet&hl=en&gl=US&ceid=US:en",
    # 한국어 검색 (구글 한국)
    "https://news.google.com/rss/search?q=네오디뮴+자석&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=희토류+자석&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=영구자석+희토류&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=망간비스무트+자석&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=희토류+재활용&hl=ko&gl=KR&ceid=KR:ko",
]

RELEVANCE_KEYWORDS = [
    "NdFeB", "neodymium", "rare earth", "MnBi", "magnet", "Nd-Fe-B",
    "permanent magnet", "magnet recycling",
    "네오디뮴", "희토류", "영구자석", "자석", "망간비스무트", "망간비스무스", "비스무트", "재활용",
]


def is_relevant(title):
    """관련 키워드 포함 여부 확인"""
    return any(kw.lower() in title.lower() for kw in RELEVANCE_KEYWORDS)


def parse_pub_date(date_str):
    """RSS pubDate → YYYY-MM-DD 파싱"""
    if not date_str:
        return ""
    date_str = date_str.strip()
    formats = [
        "%a, %d %b %Y %H:%M:%S %Z",   # Mon, 30 Mar 2026 10:00:00 GMT
        "%a, %d %b %Y %H:%M:%S %z",   # Mon, 30 Mar 2026 10:00:00 +0000
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    # 마지막 시도: 앞 25자만 파싱
    try:
        return datetime.strptime(date_str[:25], "%a, %d %b %Y %H:%M:%S").strftime("%Y-%m-%d")
    except Exception:
        return ""


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
            title_m = re.search(r"<title>(.*?)</title>",        item, re.DOTALL)
            link_m  = re.search(r"<link>(.*?)</link>",          item, re.DOTALL)
            pub_m   = re.search(r"<pubDate>(.*?)</pubDate>",    item, re.DOTALL)
            src_m   = re.search(r"<source[^>]*>(.*?)</source>", item, re.DOTALL)

            if not title_m or not link_m:
                continue

            title = re.sub(r"<[^>]+>", "", title_m.group(1)).strip()
            title = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", title).strip()
            link  = link_m.group(1).strip()
            pub_raw = pub_m.group(1).strip() if pub_m else ""
            src   = re.sub(r"<[^>]+>", "", src_m.group(1)).strip() if src_m else "Google News"

            results.append({
                "title":    title,
                "url":      link,
                "pub_date": parse_pub_date(pub_raw),   # ← 실제 기사 날짜
                "date":     pub_raw,                    # ← 원본 보관
                "source":   src,
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
                        n["source_lang"] = detect_lang(n.get("title", ""))
                    existing[url] = n
            print(f"  기존 뉴스 {len(existing)}건 로드 완료")
        except Exception as e:
            print(f"  기존 데이터 로드 실패 (첫 실행 시 정상): {e}")

    # ── RSS 수집 ──────────────────────────────────────────────────────────
    new_ko = new_en = 0
    for feed_url in RSS_FEEDS:
        kw = feed_url[feed_url.find("q=")+2 : feed_url.find("&")]
        print(f"  피드: {kw}")
        for item in parse_rss(feed_url):
            url = item.get("url", "")
            if not url or not is_relevant(item["title"]):
                continue
            if url not in existing:
                lang = detect_lang(item["title"])
                item["first_seen"]  = today_str
                item["source_lang"] = lang
                item["category"]    = classify_category(item["title"])
                existing[url] = item
                if lang == "ko":
                    new_ko += 1
                else:
                    new_en += 1

    # ── 카테고리/source_lang 없는 기존 뉴스 보완 ─────────────────────────
    for item in existing.values():
        if not item.get("category"):
            item["category"] = classify_category(item.get("title", ""))
        if not item.get("source_lang"):
            item["source_lang"] = detect_lang(item.get("title", ""))

    # ── 30일 이내 뉴스만 유지 ─────────────────────────────────────────────
    news_list = [
        n for n in existing.values()
        if n.get("first_seen", "9999-99-99") >= cutoff
    ]
    # pub_date 기준 정렬 (없으면 first_seen 사용)
    news_list.sort(
        key=lambda x: x.get("pub_date") or x.get("first_seen", ""),
        reverse=True
    )

    # ── 통계 출력 ──────────────────────────────────────────────────────────
    ko_total = sum(1 for n in news_list if n.get("source_lang") == "ko")
    en_total = sum(1 for n in news_list if n.get("source_lang") != "ko")
    print(f"\n뉴스 수집 완료:")
    print(f"  신규 → 국내 {new_ko}건 / 해외 {new_en}건")
    print(f"  전체 → 국내 {ko_total}건 / 해외 {en_total}건 / 합계 {len(news_list)}건")

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
