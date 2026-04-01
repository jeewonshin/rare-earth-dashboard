import requests
import json
import os
import re
from datetime import datetime, timedelta
from collections import Counter, defaultdict

print('뉴스 수집 중...')

CATEGORIES = {
    'NdFeB': ['NdFeB','Nd-Fe-B','네오디뮴 자석','영구자석','neodymium magnet','소결자석','네오디뮴','neodymium','praseodymium'],
    'MnBi':  ['MnBi','망간비스무트','Mn-Bi','manganese bismuth','MnBi magnet','비스무트 자석'],
    'NdFeB_Recycling': ['재활용','recycling','회수','recovery','urban mining','도시광산','폐자석','재자원화','rare earth recycl','magnet recycl','수소분쇄'],
}

RSS_FEEDS = [
    'https://news.google.com/rss/search?q=네오디뮴+자석&hl=ko&gl=KR&ceid=KR:ko',
    'https://news.google.com/rss/search?q=영구자석+희토류&hl=ko&gl=KR&ceid=KR:ko',
    'https://news.google.com/rss/search?q=NdFeB+자석&hl=ko&gl=KR&ceid=KR:ko',
    'https://news.google.com/rss/search?q=희토류+재활용&hl=ko&gl=KR&ceid=KR:ko',
    'https://news.google.com/rss/search?q=MnBi+자석&hl=ko&gl=KR&ceid=KR:ko',
    'https://news.google.com/rss/search?q=neodymium+magnet&hl=en-US&gl=US&ceid=US:en',
    'https://news.google.com/rss/search?q=NdFeB+rare+earth&hl=en-US&gl=US&ceid=US:en',
    'https://news.google.com/rss/search?q=rare+earth+recycling+magnet&hl=en-US&gl=US&ceid=US:en',
    'https://news.google.com/rss/search?q=MnBi+permanent+magnet&hl=en-US&gl=US&ceid=US:en',
    'https://news.google.com/rss/search?q=permanent+magnet+supply+chain&hl=en-US&gl=US&ceid=US:en',
]

RELEVANCE_KEYWORDS = ['자석','magnet','희토류','rare earth','neodymium','네오디뮴','NdFeB','MnBi','영구자석','permanent magnet','재활용','recycling','dysprosium','praseodymium','소결','sintered']

BLOCKED_DOMAINS = [
    'daara.co.kr','exhi.daara.co.kr','daaraexpo.com',
    'yeogie.com','kidd.co.kr','navimro.com','imarketkorea.com',
    'kkmagnet.co.kr','dhmagnet.co.kr','domagnet.co.kr',
    'magnets21.co.kr','dj8225.com','neomagnets.net',
    'jlmagnet.com','magnet.co.kr','imacmagnet.com',
    'alibaba.com','aliexpress.com','made-in-china.com',
    'indiamart.com','globalsources.com','thomasnet.com',
    'directindustry.com','tradekorea.com','ec21.com','kompass.com',
    'coupang.com','gmarket.co.kr','auction.co.kr',
    '11st.co.kr','interpark.com','shopping.naver.com',
    'tmon.co.kr','wemakeprice.com',
    'newswire.co.kr','prnews.co.kr','boannews.com',
    'prnewswire.com','businesswire.com','globenewswire.com',
    'einpresswire.com','prlog.org',
    'ec.lt','steadyincomeinvestors.com',
    'ruhrkanal.news','aplusme.me',
]

BLOCKED_TITLE_PATTERNS = [
    r'\[.*자석.*\/.*자석',
    r'Tools\s*[·•]\s*Parts',
    r'MRO\s*[·•]\s*부품',
    r'비철금속',
    r'\d{7}',
    r'J\.L\. Magnet',
    r'부품\s*[·•]\s*소재',
    r'Non-ferrous Metals',
    r'강력자석.*네오디[뮴음]|네오디[뮴음].*강력자석',
    r'\d+\s*-\s*(다아라|야후|네이버쇼핑)',
    r'\d+-Pack',
    r'\d+\s*mm\s*[Xx]\s*\d+\s*mm',
    r'\d+\s*(Gauss|gauss)',
    r'(Nickel|Zinc|Gold|Silver)\s+Plated',
    r'\d+\s*(Lbs|lbs)\b',
    r'(Bracelet|Necklace|Jewelry|Carabiner)',
    r'(Round Disc|Disc Magnet|Bar Magnet|Block Magnet)',
    r'For\s+(Fridge|Kitchen|Camping|Whiteboard)',
    r'Heavy Duty.{0,20}[Mm]agnet|[Mm]agnet.{0,20}Heavy Duty',
    r'\d+\s*(Pieces|Pcs|pcs)\s',
]


def classify_category(title, abstract=""):
    text = (title + " " + abstract).lower()
    mnbi = ["mnbi","mn-bi","ltp-mnbi","망간비스무트","manganese bismuth","bismuth manganese","비스무트 자석"]
    if any(k in text for k in mnbi): return "MnBi"
    rec  = ["재활용","recycle","recycling","recovery","회수","urban mining","도시광산","수소분쇄","폐자석","magnet recycl","rare earth recycl","end-of-life","재자원화"]
    if any(k in text for k in rec):  return "NdFeB_Recycling"
    nd   = ["ndfeb","nd-fe-b","네오디뮴","neodymium","영구자석","permanent magnet","소결자석","sintered magnet","grain boundary","coercivity","희토류 자석","praseodymium","dysprosium","terbium"]
    if any(k in text for k in nd):   return "NdFeB"
    return "기타"


def detect_lang(title):
    return "ko" if len(re.findall(r"[가-힣]", title)) > 2 else "en"


# [수정 1] source 파라미터 추가 - URL이 Google 리다이렉트라도 source로 차단
def is_relevant(title, url="", snippet="", source=""):
    # 1. 도메인 차단 (url + source 둘 다 체크)
    if any(domain in url for domain in BLOCKED_DOMAINS):
        return False
    if any(domain in source for domain in BLOCKED_DOMAINS):  # ★ 추가
        return False
    # 2. 제목 패턴 차단
    for pat in BLOCKED_TITLE_PATTERNS:
        if re.search(pat, title, re.IGNORECASE):
            return False
    # 3. 관련성 키워드 확인
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
            title  = get("title")
            link   = get("link")
            source = get("source")  # ★ [수정 2-a] 먼저 추출
            if not title: continue
            # 광고성 도메인 차단 (url + source 둘 다 체크)
            if any(domain in link   for domain in BLOCKED_DOMAINS): continue
            if any(domain in source for domain in BLOCKED_DOMAINS): continue  # ★ [수정 2-b] 추가
            # 광고성 제목 패턴 차단
            if any(re.search(p, title, re.IGNORECASE) for p in BLOCKED_TITLE_PATTERNS): continue
            dt = parse_pub_date(get("pubDate"))
            ds = dt.strftime("%Y-%m-%d") if dt else ""
            items.append({
                "title": title, "url": link,
                "pub_date": ds, "date": ds,
                "source": source,  # ★ [수정 2-c] get() 대신 변수 재사용
                "first_seen": datetime.now().strftime("%Y-%m-%d"),
                "source_lang": detect_lang(title),
                "category": classify_category(title),
            })
    except Exception as e:
        print(f"  피드 오류: {url[:60]} -> {e}")
    return items


def normalize_title(t):
    t = t.strip()
    for sep in [" - "," | "," · "," :: "," : "]:
        if sep in t: t = t[:t.rfind(sep)]
    return re.sub(r"[^\w가-힣]","",t.lower()).strip()


def similarity(s1,s2):
    if not s1 or not s2: return 0.0
    c1,c2 = Counter(s1),Counter(s2)
    return sum((c1&c2).values())/max(len(s1),len(s2))


def is_duplicate(t1,t2):
    n1,n2 = normalize_title(t1),normalize_title(t2)
    if not n1 or not n2: return False
    if n1==n2: return True
    sh,lo = (n1,n2) if len(n1)<=len(n2) else (n2,n1)
    if len(sh)>=10 and sh in lo: return True
    return similarity(n1,n2)>=0.8


def deduplicate_news(lst):
    kept,rm = [],0
    for item in lst:
        if any(is_duplicate(item.get("title",""),k.get("title","")) for k in kept): rm+=1
        else: kept.append(item)
    print(f"  중복 제거: {rm}건 -> {len(kept)}건 유지")
    return kept


def smart_retention(lst):
    MIN_PER_CAT  = 5    # 카테고리 전체 최소
    MAX_PER_CAT  = 50   # 카테고리 전체 최대
    MIN_PER_LANG = 3    # ★ 국내/해외 각각 최소 (부족하면 이전 뉴스로 보충)

    c90  = (datetime.now()-timedelta(days=90)).strftime("%Y-%m-%d")
    c365 = (datetime.now()-timedelta(days=365)).strftime("%Y-%m-%d")
    lst  = sorted(lst, key=lambda x: x.get("date",""), reverse=True)
    bkts = defaultdict(list)
    for item in lst: bkts[item.get("category","기타")].append(item)

    final = []
    for cat, items in bkts.items():
        recent   = [n for n in items if n.get("date","") >= c90]
        extended = [n for n in items if n.get("date","") >= c365]

        # 1단계: 기존 로직 (카테고리 전체 기준)
        if len(recent) >= MIN_PER_CAT:
            kept = recent[:MAX_PER_CAT]
            print(f"    [{cat}] 90일 {len(recent)}건 -> {len(kept)}건 유지")
        else:
            kept = extended[:MAX_PER_CAT] or items[:MAX_PER_CAT]
            print(f"    [{cat}] 90일 {len(recent)}건 부족 -> 1년치 {len(kept)}건 확장")

        # ★ 2단계: 국내/해외 각각 최소 보장 (NEW)
        kept_urls = {n.get("url","") for n in kept}
        for lang in ["ko", "en"]:
            lang_kept = [n for n in kept if n.get("source_lang","") == lang]
            if len(lang_kept) < MIN_PER_LANG:
                # kept에 없는 이전 뉴스에서 보충
                supplement = [
                    n for n in items
                    if n.get("source_lang","") == lang
                    and n.get("url","") not in kept_urls
                ]
                need  = MIN_PER_LANG - len(lang_kept)
                added = supplement[:need]
                kept.extend(added)
                kept_urls.update(n.get("url","") for n in added)
                if added:
                    label = "국내" if lang == "ko" else "해외"
                    print(f"      [{cat}] {label} {len(lang_kept)}건 부족 → {len(added)}건 보충")

        kept = sorted(kept, key=lambda x: x.get("date",""), reverse=True)
        final.extend(kept)

    return sorted(final, key=lambda x: x.get("date",""), reverse=True)



def main():
    news_path = "data/news.json"
    existing  = []
    try:
        with open(news_path,"r",encoding="utf-8") as f: existing=json.load(f)
        if isinstance(existing,dict): existing=existing.get("items",[])
        print(f"기존 뉴스: {len(existing)}건")
    except: print("기존 뉴스 없음")

    # ★ [수정 3-a] 기존 뉴스 소급 필터 (source + url + title 패턴 모두 체크)
    before = len(existing)
    existing = [
        n for n in existing
        if not any(d in n.get("source","") for d in BLOCKED_DOMAINS)
        and not any(d in n.get("url","")   for d in BLOCKED_DOMAINS)
        and not any(re.search(p, n.get("title",""), re.IGNORECASE) for p in BLOCKED_TITLE_PATTERNS)
    ]
    if before != len(existing):
        print(f"  ★ 기존 광고 소급 제거: {before - len(existing)}건 → {len(existing)}건 유지")

    for item in existing: item["category"]=classify_category(item.get("title",""))
    existing_fs   = {i.get("url",""): i.get("first_seen","") for i in existing}
    existing_urls = {i.get("url","") for i in existing}
    today_str = datetime.now().strftime("%Y-%m-%d")
    collected = []
    for url in RSS_FEEDS:
        items = parse_rss(url)
        print(f"  {len(items)}건: {url[50:80]}")
        collected.extend(items)
    new_items = [i for i in collected if i.get("url","") not in existing_urls]
    print(f"신규 기사: {len(new_items)}건")
    for item in new_items:
        url = item.get("url","")
        item["first_seen"] = existing_fs[url] if (url in existing_fs and existing_fs[url]) else today_str

    # news_raw.json
    raw = new_items + existing
    # ★ [수정 3-b] is_relevant에 source= 추가
    raw = [n for n in raw if is_relevant(n.get("title",""), n.get("url",""), source=n.get("source",""))]
    c90 = (datetime.now()-timedelta(days=90)).strftime("%Y-%m-%d")
    raw = [n for n in raw if n.get("date","")>=c90]
    raw.sort(key=lambda x: x.get("date",""), reverse=True)
    os.makedirs("data", exist_ok=True)
    with open("data/news_raw.json","w",encoding="utf-8") as f: json.dump(raw,f,ensure_ascii=False,indent=2)
    print(f"news_raw.json: {len(raw)}건 (중복 포함, 트렌드용)")

    # news.json
    news_list = new_items + existing
    # ★ [수정 3-c] is_relevant에 source= 추가
    news_list = [n for n in news_list if is_relevant(n.get("title",""), n.get("url",""), source=n.get("source",""))]
    news_list.sort(key=lambda x: x.get("date",x.get("pub_date","")), reverse=True)
    print("중복 제거 중...")
    news_list = deduplicate_news(news_list)
    print("스마트 보존 중...")
    news_list = smart_retention(news_list)
    ko  = sum(1 for n in news_list if n.get("source_lang")=="ko")
    cat = Counter(n.get("category","기타") for n in news_list)
    print(f"최종: {len(news_list)}건 (국내:{ko} 해외:{len(news_list)-ko})")
    for c,cnt in cat.most_common(): print(f"  [{c}] {cnt}건")
    with open(news_path,"w",encoding="utf-8") as f: json.dump(news_list,f,ensure_ascii=False,indent=2)
    print(f"저장 완료: {news_path}")


if __name__ == "__main__":
    main()
