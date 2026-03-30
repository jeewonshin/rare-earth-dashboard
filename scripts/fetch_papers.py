import requests
import json
import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta

print('논문 수집 시작 (arXiv + CrossRef) - 카테고리별 독립 수집...')

os.makedirs('data', exist_ok=True)


def normalize_date(date_str, fallback=''):
    """날짜 문자열을 YYYY-MM-DD로 정규화"""
    if not date_str:
        return fallback
    date_str = str(date_str).strip()
    try:
        if re.match(r'^\d{4}-\d{2}-\d{2}$', date_str):
            return date_str
        elif re.match(r'^\d{4}-\d{2}$', date_str):
            return date_str + '-01'
        elif re.match(r'^\d{4}$', date_str):
            return date_str + '-01-01'
        else:
            return date_str
    except Exception:
        return fallback


# ── 카테고리 정의 ─────────────────────────────────────────────────────────
CATEGORIES = {
    'NdFeB': [
        'Nd-Fe-B', 'NdFeB', 'neodymium iron boron', 'neodymium magnet',
        'sintered magnet', 'hot deformation', 'hot deform', 'hot press',
        'grain boundary diffusion', 'HPMS', 'Ce substitution', 'Ce substitut',
        'Dy substitution', 'coercivity', 'permanent magnet',
    ],
    'MnBi': [
        'MnBi', 'manganese bismuth', 'MnBi magnet',
        'hard magnetic MnBi', 'low temperature phase MnBi', 'LTP-MnBi',
    ],
    'NdFeB_Recycling': [
        'NdFeB recycling', 'NdFeB recycle', 'rare earth recycling',
        'magnet recycling', 
        'rare earth recovery', 'end-of-life magnet', 'urban mining',
    ],
}


def classify_category(title, abstract=''):
    """통계/검증용 카테고리 분류"""
    text = (title + ' ' + abstract).lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else '기타'


# ── 카테고리별 수집 설정 ───────────────────────────────────────────────────
CATEGORY_CONFIGS = [
    {
        'category': 'NdFeB',
        'arxiv_query': (
            '(ti:"Nd-Fe-B" OR ti:"NdFeB" OR ti:"neodymium magnet" OR ti:"permanent magnet"'
            ' OR abs:"Nd-Fe-B" OR abs:"NdFeB")'
            ' AND '
            '(ti:"hot deform" OR ti:"hot-deform" OR ti:"hot press"'
            ' OR ti:"Ce substitut" OR ti:"grain boundary diffusion"'
            ' OR abs:"hot deform" OR abs:"hot press"'
            ' OR abs:"Ce substitut" OR abs:"grain boundary diffusion")'
        ),
        'crossref_query': (
            '"Nd-Fe-B" OR "NdFeB" OR "neodymium magnet" '
            '"hot deform" OR "hot press" OR "Ce substituted" OR "grain boundary diffusion"'
        ),
        'must_keywords':   ['nd-fe-b', 'ndfeb', 'neodymium', 'permanent magnet'],
        'detail_keywords': ['hot deform', 'hot-deform', 'hot press', 'ce substitut',
                            'cerium substitut', 'grain boundary diffusion',
                            'coercivity', 'sintered magnet'],
        'arxiv_max':    8,
        'crossref_max': 15,
    },
    {
        'category': 'MnBi',
        'arxiv_query': (
            '(ti:"MnBi" OR ti:"manganese bismuth" OR ti:"Mn-Bi"'
            ' OR abs:"MnBi" OR abs:"manganese bismuth")'
            ' AND '
            '(ti:"magnet" OR ti:"magnetic" OR ti:"hard magnetic"'
            ' OR abs:"magnet" OR abs:"magnetic" OR abs:"hard magnetic")'
        ),
        'crossref_query': (
            '"MnBi" OR "manganese bismuth" OR "Mn-Bi magnet" '
            '"hard magnetic" OR "permanent magnet" OR "magnetic anisotropy"'
        ),
        'must_keywords':   ['mnbi', 'mn-bi', 'manganese bismuth'],
        'detail_keywords': ['magnet', 'magnetic', 'hard magnetic',
                            'anisotropy', 'coercivity', 'ltp-mnbi',
                            'low temperature phase'],
        'arxiv_max':    5,
        'crossref_max': 10,
    },
    {
        'category': 'NdFeB_Recycling',
        'arxiv_query': (
            '(ti:"NdFeB recycling" OR ti:"rare earth recycling"'
            ' OR ti:"magnet recycling" '
            ' OR abs:"NdFeB recycling" OR abs:"rare earth recycling" )'
            ' AND '
            '(ti:"magnet" OR ti:"rare earth" OR ti:"neodymium"'
            ' OR abs:"magnet" OR abs:"rare earth")'
        ),
        'crossref_query': (
            '"NdFeB recycling" OR "rare earth recycling" OR "magnet recycling" '
            'OR "rare earth recovery"'
        ),
        'must_keywords':   ['recycling', 'recycle', 'recovery',
                           ],
        'detail_keywords': ['magnet', 'rare earth', 'neodymium',
                            'nd-fe-b', 'ndfeb', 'urban mining', 'end-of-life'],
        'arxiv_max':    5,
        'crossref_max': 10,
    },
]


# ── 기존 papers.json 로드 ─────────────────────────────────────────────────
existing_urls       = set()
existing_first_seen = {}
if os.path.exists('data/papers.json'):
    try:
        with open('data/papers.json', 'r', encoding='utf-8') as f:
            old_data = json.load(f)
            for p in old_data.get('items', []):
                url = p.get('url', '')
                if url:
                    existing_urls.add(url)
                if url and p.get('first_seen'):
                    existing_first_seen[url] = p['first_seen']
        print(f'  기존 논문 {len(existing_urls)}건 로드 완료')
    except Exception as e:
        print(f'  기존 데이터 로드 실패 (첫 실행 시 정상): {e}')


# ── 카테고리별 수집 ───────────────────────────────────────────────────────
all_papers  = []
seen_titles = set()   # 전체 공유 - 카테고리 간 중복 제거

for cfg in CATEGORY_CONFIGS:
    cat          = cfg['category']
    must_kws     = cfg['must_keywords']
    detail_kws   = cfg['detail_keywords']
    arxiv_papers = []
    cr_papers    = []

    print(f'\n  ── [{cat}] 수집 중 ──')

    # ── arXiv ──
    try:
        res = requests.get(
            'https://export.arxiv.org/api/query',
            params={
                'search_query': cfg['arxiv_query'],
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

            # 5년 필터
            try:
                pub_dt = datetime.strptime(date_raw, '%Y-%m-%d').date()
                if (datetime.now().date() - pub_dt).days > 365 * 5:
                    continue
            except Exception:
                pass

            text_lower = (title + ' ' + abstract).lower()
            has_must   = any(k in text_lower for k in must_kws)
            has_detail = any(k in text_lower for k in detail_kws)

            if not (has_must and has_detail):
                continue
            if title in seen_titles:
                continue

            seen_titles.add(title)
            arxiv_papers.append({
                'title':    title,
                'authors':  ', '.join(authors[:3]) + (' et al.' if len(authors) > 3 else ''),
                'date':     date_raw,
                'sort_date':date_raw,
                'url':      url,
                'abstract': abstract[:200] + '...',
                'source':   'arXiv',
                'category': cat,   # 강제 할당
            })

        arxiv_papers.sort(key=lambda x: x['sort_date'], reverse=True)
        arxiv_papers = arxiv_papers[:cfg['arxiv_max']]
        print(f'    arXiv  {len(arxiv_papers)}건')

    except Exception as e:
        print(f'    arXiv 실패: {e}')

    # ── CrossRef ──
    try:
        from_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')
        today     = datetime.now().date()

        res = requests.get(
            'https://api.crossref.org/works',
            params={
                'query':  cfg['crossref_query'],
                'filter': 'from-pub-date:' + from_date + ',type:journal-article',
                'rows':   100,
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

            text_lower  = (title + ' ' + abstract_clean).lower()
            title_lower = title.lower()
            has_must    = any(k in text_lower for k in must_kws)
            has_detail  = any(k in text_lower for k in detail_kws)

            if abstract_clean.strip():
                if not (has_must and has_detail):
                    continue
            else:
                if not (any(k in title_lower for k in must_kws) and
                        any(k in title_lower for k in detail_kws)):
                    continue

            # 날짜 처리
            accepted_parts = item.get('accepted', {}).get('date-parts', [[]])[0]
            pub_parts      = item.get('published', {}).get('date-parts', [['']])[0]
            if accepted_parts:
                date_str = '-'.join(str(x).zfill(2) for x in accepted_parts if x) or ''
            else:
                date_str = '-'.join(str(x).zfill(2) for x in pub_parts if x) or ''

            try:
                check_str = normalize_date(date_str)[:7]
                if datetime.strptime(check_str, '%Y-%m').date() > today:
                    sort_date = today.strftime('%Y-%m-%d')
                else:
                    sort_date = normalize_date(date_str)
            except Exception:
                sort_date = normalize_date(date_str)

            authors_raw = item.get('author', [])
            authors_str = ', '.join(
                (a.get('given', '') + ' ' + a.get('family', '')).strip()
                for a in authors_raw[:3]
            ) + (' et al.' if len(authors_raw) > 3 else '')

            journal = item.get('container-title', [''])[0]
            url     = item.get('URL', '#')

            seen_titles.add(title)
            cr_papers.append({
                'title':    title,
                'authors':  authors_str,
                'date':     date_str,
                'sort_date':sort_date,
                'url':      url,
                'abstract': abstract_clean[:200] + '...' if abstract_clean.strip() else '',
                'source':   'CrossRef (' + journal + ')' if journal else 'CrossRef',
                'category': cat,   # 강제 할당
            })

        cr_papers.sort(key=lambda x: x.get('sort_date', x['date']), reverse=True)
        cr_papers = cr_papers[:cfg['crossref_max']]
        print(f'    CrossRef {len(cr_papers)}건')

    except Exception as e:
        print(f'    CrossRef 실패: {e}')

    all_papers.extend(arxiv_papers)
    all_papers.extend(cr_papers)


# ── 전체 정렬 ─────────────────────────────────────────────────────────────
all_papers.sort(key=lambda x: x.get('sort_date', x['date']), reverse=True)
print(f'\n  총 수집: {len(all_papers)}건')


# ── first_seen / is_new 처리 ──────────────────────────────────────────────
today_str  = datetime.now().strftime('%Y-%m-%d')
today_date = datetime.now().date()

for p in all_papers:
    url = p.get('url', '')
    if url in existing_first_seen:
        p['first_seen'] = normalize_date(existing_first_seen[url], today_str)
    elif url in existing_urls:
        p['first_seen'] = normalize_date(p.get('sort_date', p.get('date', today_str)), today_str)
    elif not existing_urls:
        p['first_seen'] = normalize_date(p.get('sort_date', p.get('date', today_str)), today_str)
    else:
        p['first_seen'] = normalize_date(
        p.get('sort_date', p.get('date', today_str)), today_str
    )


    try:
        first_seen_date = datetime.strptime(p['first_seen'], '%Y-%m-%d').date()
        p['is_new'] = (today_date - first_seen_date).days <= 30
    except Exception:
        p['is_new'] = False

new_count = sum(1 for p in all_papers if p['is_new'])
print(f'신규 논문 (30일 이내): {new_count}건 / 전체: {len(all_papers)}건')

# ── 카테고리별 통계 출력 ───────────────────────────────────────────────────
cat_counts = {}
for p in all_papers:
    cat = p.get('category', '기타')
    cat_counts[cat] = cat_counts.get(cat, 0) + 1
for cat, cnt in cat_counts.items():
    print(f'  [{cat}] {cnt}건')

output = {
    'updated':    datetime.now().strftime('%Y-%m-%d %H:%M'),
    'source':     'arXiv + CrossRef',
    'new_count':  new_count,
    'categories': list(CATEGORIES.keys()),
    'items':      all_papers,
}

with open('data/papers.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('data/papers.json 저장 완료!')
