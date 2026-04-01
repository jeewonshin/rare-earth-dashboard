import requests
import json
import os
import re
from datetime import datetime, timedelta, timezone
from collections import Counter

print("📰 뉴스 수집 중...")

# ── 카테고리 키워드 (참고용) ─────────────────────────────────────────────────
CATEGORIES = {
    "NdFeB": [
        "NdFeB", "Nd-Fe-B", "네오디뮴 자석", "영구자석", "네오디뮴자석",
        "ndfeb", "neodymium magnet", "sintered magnet", "소결자석",
        "네오디뮴", "neodymium", "praseodymium", "프라세오디뮴",
    ],
    "MnBi": [
        "MnBi", "망간비스무트", "Mn-Bi", "manganese bismuth",
        "hard magnetic", "경자성", "MnBi magnet", "비스무트 자석",
    ],
    "NdFeB_Recycling": [
        "재활용", "recycling", "회수", "recovery", "urban mining",
        "도시광산", "폐자석", "재자원화", "희토류 재활용",
        "rare earth recycl", "magnet recycl", "수소분쇄",
    ],
}

# ── RSS 피드 목록 ────────────────────────────────────────────────────────────
RSS_FEEDS = [
    "https://news.google.com/rss/search?q=네오디뮴+자석&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=영구자석+희토류&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=NdFeB+자석&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=희토류+재활용&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=MnBi+자석&hl=ko&gl=KR&ceid=KR:ko",
    "https://news.google.com/rss/search?q=neodymium+magnet&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=NdFeB+rare+earth&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=rare+earth+recycling+magnet&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=MnBi+permanent+magnet&hl=en-US&gl=US&ceid=US:en",
    "https://news.google.com/rss/search?q=permanent+magnet+supply+chain&hl=en-US&gl=US&ceid=US:en",
]

RELEVANCE_KEYWORDS = [
    "자석", "magnet", "희토류", "rare earth", "neodymium", "네오디뮴",
    "NdFeB", "MnBi", "영구자석", "permanent magnet", "재활용", "recycling",
    "dysprosium", "praseodymium", "terbium", "소결", "sintered",
]


# ── ✅ 우선순위 기반 카테고리 분류 ────────────────────────────────────────────
def classify_category(title, abstract=""):
    """
    우선순위 기반 분류 (오분류 방지):
      1순위: MnBi  — 가장 구체적, 최우선 확정
      2순위: NdFeB_Recycling
      3순위: NdFeB — 가장 일반적
      기본:  기타
    """
    text = (title + " " + abstract).lower()

    # 1순위: MnBi (MnBi 키워드 있으면 무조건 MnBi)
    mnbi_keys = [
        "mnbi", "mn-bi", "ltp-mnbi",
        "망간비스무트", "망간비스무스",
        "manganese bismuth", "bismuth manganese",
        "비스무트 자석", "비스무트자석",
    ]
    if any(kw in text for kw in mnbi_keys):
        return "MnBi"

    # 2순위: NdFeB_Recycling
    recycle_keys = [
        "재활용", "recycle", "recycling", "recovery", "회수",
        "urban mining", "도시광산", "수소분쇄", "폐자석",
        "hydrogen decrepitation", "magnet recycl",
        "rare earth recycl", "end-of-life", "재자원화",
    ]
    if any(kw in text for kw in recycle_keys):
        return "NdFeB_Recycling"

    # 3순위: NdFeB
    ndfeb_keys = [
        "ndfeb", "nd-fe-b", "네오디뮴", "neodymium",
        "영구자석", "permanent magnet", "소결자석", "sintered magnet",
        "grain boundary", "hot deform", "coercivity",
        "희토류 자석", "rare earth magnet", "프라세오디뮴",
        "praseodymium", "dysprosium", "terbium",
    ]
    if any(kw in text for kw in ndfeb_keys):
        return "NdFeB"

    return "기타"


def detect_lang(title):
    ko_chars = len(re.findall(r"[가-힣]", title))
    return "ko" if ko_chars > 2 else "en"


def is_relevant(title, snippet=""):
    text = (title + " " + snippet).lower()
    return any(kw.lower() in text for kw in RELEVANCE_KEYWORDS)


def parse_pub_date(date_str):
    if not date_str:
        return None
    for fmt in [
        "%a, %d %b %Y %H:%M:%S %Z",
        "%a, %d %b %Y %H:%M:%S %z",
        "%Y-%m-%dT%H:%M:%SZ",
    ]:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except:
            pass
    return None


def parse_rss(url):
    items = []
    try:
        resp = requests.get(url, timeout=20,
                            headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        text = resp.text

        for block in re.findall(r"<item>(.*?)</item>", text, re.DOTALL):
            def get(tag):
                m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.DOTALL)
                return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""

            title   = get("title")
            link    = get("link")
            pubdate = get("pubDate")
            source  = get("source")

            if not title:
                continue

            dt = parse_pub_date(pubdate)
            date_str = dt.strftime("%Y-%m-%d") if dt else ""

            items.append({
                "title":       title,
                "url":         link,
                "pub_date":    date_str,
                "date":        date_str,
                "source":      source,
                "first_seen":  datetime.now().strftime("%Y-%m-%d"),
                "source_lang": detect_lang(title),
                "category":    classify_category(title),
                "_dt":         dt,
            })
    except Exception as e:
        print(f"  ⚠️  피드 오류: {url[:60]} → {e}")
    return items


# ── 중복 제거 함수 ──────────────────────────────────────────────────────────

def normalize_title(title):
    t = title.strip()
    for sep in [" - ", " | ", " · ", " :: ", " : "]:
        if sep in t:
            t = t[: t.rfind(sep)]
    t = t.lower()
    t = re.sub(r"[^\w가-힣]", "", t)
    return t.strip()


def similarity(s1, s2):
    if not s1 or not s2:
        return 0.0
    c1, c2 = Counter(s1), Counter(s2)
    common = sum((c1 & c2).values())
    return common / max(len(s1), len(s2))


def is_duplicate(title1, title2):
    n1 = normalize_title(title1)
    n2 = normalize_title(title2)
    if not n1 or not n2:
        return False
    if n1 == n2:
        return True
    shorter, longer = (n1, n2) if len(n1) <= len(n2) else (n2, n1)
    if len(shorter) >= 10 and shorter in longer:
        return True
    if similarity(n1, n2) >= 0.8:
        return True
    return False


def deduplicate_news(news_list):
    kept = []
    removed = 0
    for item in news_list:
        title = item.get("title", "")
        is_dup = any(is_duplicate(title, k.get("title", "")) for k in kept)
        if is_dup:
            removed += 1
        else:
            kept.append(item)
    print(f"  중복 제거: {removed}건 제거 → {len(kept)}건 유지")
    return kept


# ── 메인 ─────────────────────────────────────────────────────────────────────

def main():
    existing = []
    news_path = "data/news.json"
    try:
        with open(news_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if isinstance(existing, dict):
            existing = existing.get("items", [])
        print(f"📂 기존 뉴스 로드: {len(existing)}건")
    except:
        print("📂 기존 뉴스 없음 (첫 실행)")

    # ── ✅ 기존 데이터도 재분류 (이전에 잘못 분류된 것 수정)
    print("🔄 기존 뉴스 카테고리 재분류 중...")
    for item in existing:
        item["category"] = classify_category(item.get("title", ""))

    # RSS 수집
    collected = []
    for url in RSS_FEEDS:
        items = parse_rss(url)
        print(f"  ✅ {len(items)}건: {url[50:90]}...")
        collected.extend(items)

    # 기존 데이터와 병합 (URL 기준)
    existing_urls = {item["url"] for item in existing}
    new_items = [i for i in collected if i["url"] not in existing_urls]
    print(f"\n신규 기사: {len(new_items)}건")

    news_list = existing + new_items

    # 관련성 필터
    news_list = [n for n in news_list if is_relevant(n.get("title", ""))]

    # 30일 이내 필터 + 정렬
    cutoff = (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")
    news_list = [n for n in news_list if n.get("date", "") >= cutoff]
    news_list.sort(key=lambda x: x.get("date", ""), reverse=True)

    # 중복 제거
    print("\n중복 뉴스 제거 중...")
    news_list = deduplicate_news(news_list)

    # _dt 필드 제거
    for item in news_list:
        item.pop("_dt", None)

    # 통계
    ko_cnt  = sum(1 for n in news_list if n.get("source_lang") == "ko")
    en_cnt  = len(news_list) - ko_cnt
    cat_cnt = Counter(n.get("category", "기타") for n in news_list)
    print(f"\n📊 최종 뉴스: {len(news_list)}건")
    print(f"   국내: {ko_cnt}건 / 해외: {en_cnt}건")
    for cat, cnt in cat_cnt.most_common():
        print(f"   [{cat}] {cnt}건")

    # 저장
    os.makedirs("data", exist_ok=True)
    with open(news_path, "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 저장 완료: data/news.json ({len(news_list)}건)")


if __name__ == "__main__":
    main()
