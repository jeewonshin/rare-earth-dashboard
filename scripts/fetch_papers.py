import requests
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

print('논문 수집 시작 (arXiv + CrossRef)...')

os.makedirs('data', exist_ok=True)

ARXIV_QUERY = (
    '(ti:"permanent magnet" OR ti:"Nd-Fe-B" OR ti:"NdFeB" OR ti:"rare earth magnet"'
    ' OR abs:"permanent magnet" OR abs:"Nd-Fe-B" OR abs:"NdFeB" OR abs:"rare earth magnet")'
    ' AND '
    '(ti:"hot deform" OR ti:"hot-deform" OR ti:"hot press"'
    ' OR ti:"Ce substitut" OR ti:"Ce-substitut" OR ti:"cerium substitut"'
    ' OR ti:"grain boundary diffusion"'
    ' OR abs:"hot deform" OR abs:"hot-deform" OR abs:"hot press"'
    ' OR abs:"Ce substitut" OR abs:"Ce-substitut" OR abs:"cerium substitut"'
    ' OR abs:"grain boundary diffusion")'
)

CROSSREF_QUERY = (
    '"permanent magnet" OR "Nd-Fe-B" OR "NdFeB" OR "rare earth magnet" '
    '"hot deform" OR "hot press" OR "Ce substituted" OR "grain boundary diffusion"'
)

MUST_KEYWORDS   = ['permanent magnet', 'nd-fe-b', 'ndfeb', 'rare earth magnet']
DETAIL_KEYWORDS = ['hot deform', 'hot-deform', 'hot press', 'ce substitut', 'ce-substitut', 'cerium substitut', 'grain boundary diffusion']

arxiv_papers    = []
crossref_papers = []
seen_titles     = set()

# ★ 기존 papers.json 로드 → url -> first_seen 매핑 저장
existing_first_seen = {}
if os.path.exists('data/papers.json'):
    try:
        with open('data/papers.json', 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            for p in old_data.get('items', []):
                url = p.get('url', '')
                if url and p.get('first_seen'):
                    existing_first_seen[url] = p['first_seen']
        existing_urls = set(existing_first_seen.keys())
        print(f'  기존 논문 {len(existing_urls)}건 로드 완료')
    except Exception as e:
        existing_urls = set()
        print(f'  기존 데이터 로드 실패 (첫 실행 시 정상): {e}')
else:
    existing_urls = set()


# ── arXiv API ──────────────────────────────────────────────────────────────
print('  [1/2] arXiv 수집 중...')

try:
    res = requests.get(
        'https://export.arxiv.org/api/query',
        params={
            'search_query': ARXIV_QUERY,
            'start':        0,
            'max_results':  100,
            'sortBy':       'submittedDate',
            'sortOrder':    'descending',
        },
        timeout=20
    )

    ns   = {'atom': 'http://www.w3.org/2005/Atom'}
    root = ET.fromstring(res.text)

    for entry in root.findall('atom:entry', ns):
        title    = entry.find('atom:title',     ns).text.strip().replace('\n', ' ')
        url      = entry.find('atom:id',        ns).text.strip()
        date_raw = entry.find('atom:published', ns).text.strip()[:10]
        authors  = [a.find('atom:name', ns).text for a in entry.findall('atom:author', ns)]
        abstract = entry.find('atom:summary',   ns).text.strip().replace('\n', ' ')

        # 날짜 필터: 5년 이내만
        try:
            pub_dt   = datetime.strptime(date_raw, '%Y-%m-%d').date()
            days_old = (datetime.now().date() - pub_dt).days
            if days_old > 365 * 5:
                continue
        except Exception:
            pass

        text_lower = (title + ' ' + abstract).lower()
        has_must   = any(k in text_lower for k in MUST_KEYWORDS)
        has_detail = any(k in text_lower for k in DETAIL_KEYWORDS)

        if not (has_must and has_detail):
            continue

        if title not in seen_titles:
            seen_titles.add(title)
            arxiv_papers.append({
                'title':     title,
                'authors':   ', '.join(authors[:3]) + (' et al.' if len(authors) > 3 else ''),
                'date':      date_raw,
                'sort_date': date_raw,  # arXiv는 미래 날짜 없으므로 동일
                'url':       url,
                'abstract':  abstract[:200] + '...',
                'source':    'arXiv',
            })

    print(f'  arXiv {len(arxiv_papers)}건 수집')

except Exception as e:
    print(f'  arXiv 실패: {e}')


# ── CrossRef API ───────────────────────────────────────────────────────────
print('  [2/2] CrossRef 수집 중...')

try:
    from_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
    today     = datetime.now().date()

    res = requests.get(
        'https://api.crossref.org/works',
        params={
            'query':  CROSSREF_QUERY,
            'filter': 'from-pub-date:' + from_date + ',type:journal-article',
            'rows':   200,
            'sort':   'relevance',
            'select': 'title,author,published,accepted,URL,abstract,container-title',
        },
        headers={'User-Agent': 'RareEarthDashboard/1.0 (research tool)'},
        timeout=20
    )

    items = res.json().get('message', {}).get('items', [])

    for item in items:
        title_list = item.get('title', [])
        if not title_list:
            continue
        title = title_list[0].strip()
        if title in seen_titles:
            continue

        abstract_raw   = item.get('abstract', '')
        abstract_clean = re.sub(r'<[^>]+>', '', abstract_raw)

        title_lower = title.lower()
        text_lower  = (title + ' ' + abstract_clean).lower()
        has_must    = any(k in text_lower for k in MUST_KEYWORDS)
        has_detail  = any(k in text_lower for k in DETAIL_KEYWORDS)

        # abstract 유무에 따라 필터링 완화
        if abstract_clean.strip():
            if not (has_must and has_detail):
                continue
        else:
            has_must_in_title   = any(k in title_lower for k in MUST_KEYWORDS)
            has_detail_in_title = any(k in title_lower for k in DETAIL_KEYWORDS)
            if not (has_must_in_title and has_detail_in_title):
                continue

        # ★ 날짜 처리: accepted 우선 → published
        accepted_parts = item.get('accepted', {}).get('date-parts', [[]])[0]
        pub_parts      = item.get('published', {}).get('date-parts', [['']])[0]

        if accepted_parts:
            date_str = '-'.join(str(x).zfill(2) for x in accepted_parts if x) or ''
        else:
            date_str = '-'.join(str(x).zfill(2) for x in pub_parts if x) or ''

        # ★ 미래 날짜면 sort_date만 오늘로 대체, date는 원본 유지 (표시용)
        try:
            check_str = date_str[:7] if len(date_str) >= 7 else date_str
            if datetime.strptime(check_str, '%Y-%m').date() > today:
                sort_date = today.strftime('%Y-%m-%d')
            else:
                sort_date = date_str
        except Exception:
            sort_date = date_str

        authors_raw = item.get('author', [])
        authors_str = ', '.join(
            (a.get('given', '') + ' ' + a.get('family', '')).strip()
            for a in authors_raw[:3]
        ) + (' et al.' if len(authors_raw) > 3 else '')

        journal = item.get('container-title', [''])[0]
        url     = item.get('URL', '#')

        seen_titles.add(title)
        crossref_papers.append({
            'title':     title,
            'authors':   authors_str,
            'date':      date_str,   # 원본 날짜 (화면 표시용)
            'sort_date': sort_date,  # 정렬용 (미래면 오늘로 대체)
            'url':       url,
            'abstract':  abstract_clean[:200] + '...' if abstract_clean.strip() else '',
            'source':    'CrossRef (' + journal + ')' if journal else 'CrossRef',
        })

    print(f'  CrossRef {len(crossref_papers)}건 수집')

except Exception as e:
    print(f'  CrossRef 실패: {e}')


# ── 합치기: arXiv 상위 10건 + CrossRef 상위 20건 ───────────────────────────
arxiv_papers.sort(key=lambda x: x.get('sort_date', x['date']),    reverse=True)
crossref_papers.sort(key=lambda x: x.get('sort_date', x['date']), reverse=True)

papers = arxiv_papers[:10] + crossref_papers[:20]
papers.sort(key=lambda x: x.get('sort_date', x['date']), reverse=True)

print(f'  arXiv 상위 10건 + CrossRef 상위 20건 = 총 {len(papers)}건')

# ★ first_seen 기록 + is_new 판단 (first_seen 기준 30일 이내면 NEW)
today_str  = datetime.now().strftime('%Y-%m-%d')
today_date = datetime.now().date()

for p in papers:
    url = p.get('url', '')
    if url in existing_first_seen:
        # 기존 논문 → first_seen 유지
        p['first_seen'] = existing_first_seen[url]
    else:
        if not existing_first_seen:
            # 첫 실행 → sort_date 기준으로 세팅 (미래 논문은 오늘, 오래된 건 실제 날짜)
            p['first_seen'] = p.get('sort_date', p.get('date', today_str))[:10]
        else:
            # 이후 실행 → 오늘 날짜 (진짜 새 논문)
            p['first_seen'] = today_str

    # ★ first_seen 기준 30일 이내면 NEW (웹 표시용)
    try:
        first_seen_date = datetime.strptime(p['first_seen'], '%Y-%m-%d').date()
        p['is_new'] = (today_date - first_seen_date).days <= 30
    except Exception:
        p['is_new'] = True

new_count = sum(1 for p in papers if p['is_new'])
print(f'신규 논문 (first_seen 기준 30일 이내): {new_count}건 / 전체: {len(papers)}건')

output = {
    'updated':   datetime.now().strftime('%Y-%m-%d %H:%M'),
    'source':    'arXiv + CrossRef',
    'new_count': new_count,
    'items':     papers,
}

with open('data/papers.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('data/papers.json 저장 완료!')
