import requests
import json
import os
import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict

print("📰 뉴스 수집 중...")

CATEGORIES = {
    "NdFeB": ["NdFeB","Nd-Fe-B","네오디뮴 자석","영구자석","neodymium magnet","sintered magnet","소결자석","네오디뮴","neodymium","praseodymium"],
    "MnBi":  ["MnBi","망간비스무트","Mn-Bi","manganese bismuth","MnBi magnet","비스무트 자석"],
    "NdFeB_Recycling": ["재활용","recycling","회수","recovery","urban mining","도시광산","폐자석","재자원화","rare earth recycl","magnet recycl","수소분쇄"],
}

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
    "자석","magnet","희토류","rare earth","neodymium","네오디뮴",
    "NdFeB","MnBi","영구자석","permanent magnet","재활용","recycling",
    "dysprosium","praseodymium","소결","sintered",
]

def classify_category(title, abstract=""):
    text = (title + " " + abstract).lower()
    mnbi_keys = ["mnbi","mn-bi","ltp-mnbi","망간비스무트","manganese bismuth","bismuth manganese","비스무트 자석"]
    if any(kw in text for kw in mnbi_keys): return "MnBi"
    recycle_keys = ["재활용","recycle","recycling","recovery","회수","urban mining","도시광산","수소분쇄","폐자석","magnet recycl","rare earth recycl","end-of-life","재자원화"]
    if any(kw in text for kw in recycle_keys): return "NdFeB_Recycling"
    ndfeb_keys = ["ndfeb","nd-fe-b","네오디뮴","neodymium","영구자석","permanent magnet","소결자석","sintered magnet","grain boundary","coercivity","희토류 자석","praseodymium","dysprosium","terbium"]
    if any(kw in text for kw in ndfeb_keys): return "NdFeB"
    return "기타"

def detect_lang(title):
    return "ko" if len(re.findall(r"[가-힣]", title)) > 2 else "en"

def is_relevant(title, snippet=""):
    text = (title + " " + snippet).lower()
    return any(kw.lower() in text for kw in RELEVANCE_KEYWORDS)

def parse_pub_date(date_str):
    if not date_str: return None
    for fmt in ["%a, %d %b %Y %H:%M:%S %Z","%a, %d %b %Y %H:%M:%S %z","%Y-%m-%dT%H:%M:%SZ"]:
        try: return datetime.strptime(date_str.strip(), fmt)
        except: pass
    return None

def parse_rss(url):
    items = []
    try:
        resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        for block in re.findall(r"<item>(.*?)</item>", resp.text, re.DOTALL):
            def get(tag, b=block):
                m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", b, re.DOTALL)
                return re.sub(r"<[^>]+>", "", m.group(1)).strip() if m else ""
            title = get("title")
            if not title: continue
            dt = parse_pub_date(get("pubDate"))
            date_str = dt.strftime("%Y-%m-%d") if dt else ""
            items.append({
                "title":       title,
                "url":         get("link"),
                "pub_date":    date_str,
                "date":        date_str,
                "source":      get("source"),
                "first_seen":  datetime.now().strftime("%Y-%m-%d"),
                "source_lang": detect_lang(title),
                "category":    classify_category(title),
            })
    except Exception as e:
        print(f"  ⚠️  피드 오류: {url[:60]} -> {e}")
    return items

def normalize_title(title):
    t = title.strip()
    for sep in [" - "," | "," · "," :: "," : "]:
        if sep in t: t = t[:t.rfind(sep)]
    t = re.sub(r"[^\w가-힣]", "", t.lower())
    return t.strip()

def similarity(s1, s2):
    if not s1 or not s2: return 0.0
    c1, c2 = Counter(s1), Counter(s2)
    return sum((c1 & c2).values()) / max(len(s1), len(s2))

def is_duplicate(t1, t2):
    n1, n2 = normalize_title(t1), normalize_title(t2)
    if not n1 or not n2: return False
    if n1 == n2: return True
    sh, lo = (n1, n2) if len(n1) <= len(n2) else (n2, n1)
    if len(sh) >= 10 and sh in lo: return True
    return similarity(n1, n2) >= 0.8

def deduplicate_news(news_list):
    kept, removed = [], 0
    for item in news_list:
        if any(is_duplicate(item.get("title",""), k.get("title","")) for k in kept):
            removed += 1
        else:
            kept.append(item)
    print(f"  중복 제거: {removed}건 제거 -> {len(kept)}건 유지")
    return kept

def smart_retention(news_list):
    """
    카테고리별 스마트 보존:
    - MIN_PER_CAT=5 (5건 미만이면 1년치 확장)
    - MAX_PER_CAT=50
    """
    MIN_PER_CAT   = 5    # ✅ 10 → 5로 낮춤 (국내 뉴스 적은 카테고리 보호)
    MAX_PER_CAT   = 50
    DAYS_DEFAULT  = 90
    DAYS_EXTENDED = 365

    cutoff_90d  = (datetime.now() - timedelta(days=DAYS_DEFAULT)).strftime("%Y-%m-%d")
    cutoff_365d = (datetime.now() - timedelta(days=DAYS_EXTENDED)).strftime("%Y-%m-%d")

    news_list = sorted(news_list, key=lambda x: x.get("date",""), reverse=True)
    buckets = defaultdict(list)
    for item in news_list:
        buckets[item.get("category","기타")].append(item)

    print("\n  [스마트 보존 결과]")
    final = []
    for cat, items in buckets.items():
        recent   = [n for n in items if n.get("date","") >= cutoff_90d]
        extended = [n for n in items if n.get("date","") >= cutoff_365d]
        if len(recent) >= MIN_PER_CAT:
            kept = recent[:MAX_PER_CAT]
            print(f"    [{cat}] 90일 {len(recent)}건 → {len(kept)}건 유지 ✅")
        else:
            kept = extended[:MAX_PER_CAT]
            if not kept:
                kept = items[:MAX_PER_CAT]
            print(f"    [{cat}] 90일 {len(recent)}건 부족 → {len(kept)}건 유지 (확장) ⚠️")
        final.extend(kept)
    return sorted(final, key=lambda x: x.get("date",""), reverse=True)


def main():
    news_path = "data/news.json"
    existing  = []
    try:
        with open(news_path, "r", encoding="utf-8") as f:
            existing = json.load(f)
        if isinstance(existing, dict):
            existing = existing.get("items", [])
        print(f"📂 기존 뉴스 로드: {len(existing)}건")
    except:
        print("📂 기존 뉴스 없음 (첫 실행)")

    # 기존 데이터 재분류
    print("🔄 기존 뉴스 카테고리 재분류 중...")
    for item in existing:
        item["category"] = classify_category(item.get("title",""))

    # ✅ FIX 1: first_seen 보존 맵 생성
    existing_fs  = {item.get("url",""): item.get("first_seen","") for item in existing}
    existing_urls = {item.get("url","") for item in existing}
    today_str = datetime.now().strftime("%Y-%m-%d")

    # RSS 수집
    collected = []
    for url in RSS_FEEDS:
        items = parse_rss(url)
        print(f"  ✅ {len(items)}건: {url[50:90]}...")
        collected.extend(items)

    # URL 기준 신규만 필터
    new_items = [i for i in collected if i.get("url","") not in existing_urls]
    print(f"\n신규 기사: {len(new_items)}건")

    # ✅ FIX 2: 신규 기사 first_seen 설정 (기존 있으면 보존, 없으면 오늘)
    for item in new_items:
        url = item.get("url","")
        if url in existing_fs and existing_fs[url]:
            item["first_seen"] = existing_fs[url]
        else:
            item["first_seen"] = today_str

    # ✅ FIX 3: 신규 기사를 앞에! (중복 제거 시 최신 기사 보존)
    news_list = new_items + existing

    # 관련성 필터
    news_list = [n for n in news_list if is_relevant(n.get("title",""))]

    # ✅ FIX 4: 중복 제거 전 최신순 정렬 (최신 기사가 살아남도록)
    news_list.sort(key=lambda x: x.get("date", x.get("pub_date","")), reverse=True)
    print("\n중복 뉴스 제거 중...")
    news_list = deduplicate_news(news_list)

    # 스마트 보존
    print("\n스마트 보존 로직 적용 중...")
    news_list = smart_retention(news_list)

    # 통계
    ko  = sum(1 for n in news_list if n.get("source_lang") == "ko")
    cat = Counter(n.get("category","기타") for n in news_list)
    print(f"\n📊 최종 뉴스: {len(news_list)}건")
    print(f"   국내: {ko}건 / 해외: {len(news_list)-ko}건")
    for c, cnt in cat.most_common():
        print(f"   [{c}] {cnt}건")

    os.makedirs("data", exist_ok=True)
    with open(news_path, "w", encoding="utf-8") as f:
        json.dump(news_list, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 저장 완료: data/news.json ({len(news_list)}건)")


if __name__ == "__main__":
    main()
