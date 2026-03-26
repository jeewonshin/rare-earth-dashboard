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

MUST_KEYWORDS   = ['permanent magnet', 'nd', 'neodymium', 'rare earth magnet']
DETAIL_KEYWORDS = ['hot deform', 'hot-deform', 'hot press', 'ce substitut', 'ce-substitut', 'cerium substitut', 'grain boundary diffusion']

arxiv_papers    = []
crossref_papers = []
seen_titles     = set()


# arXiv API
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
                'title':    title,
                'authors':  ', '.join(authors[:3]) + (' et al.' if len(authors) > 3 else ''),
                'date':     date_raw,
                'url':      url,
                'abstract': abstract[:200] + '...',
                'source':   'arXiv',
            })

    print(f'  arXiv {len(arxiv_papers)}건 수집')

except Exception as e:
    print(f'  arXiv 실패: {e}')


# CrossRef API
print('  [2/2] CrossRef 수집 중...')

try:
    from_date = (datetime.now() - timedelta(days=365*5)).strftime('%Y-%m-%d')

    res = requests.get(
        'https://api.crossref.org/works',
        params={
            'query':  CROSSREF_QUERY,
            'filter': 'from-pub-date:' + from_date + ',type:journal-article',
            'rows':   200,          # 50 → 200으로 확대
            'sort':   'relevance',  # published → relevance로 변경
            'select': 'title,author,published,URL,abstract,container-title',
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

        title_lower    = title.lower()
        text_lower     = (title + ' ' + abstract_clean).lower()
        has_must       = any(k in text_lower for k in MUST_KEYWORDS)
        has_detail     = any(k in text_lower for k in DETAIL_KEYWORDS)

        # ★ 수정된 필터링 로직
        # abstract가 있으면 기존과 동일하게 must+detail 둘 다 요구
        # abstract가 없으면 (제목만 있는 경우) must 키워드만 있어도 통과 + 제목에 detail 키워드 체크
        if abstract_clean.strip():
            if not (has_must and has_detail):
                continue
        else:
            has_must_in_title   = any(k in title_lower for k in MUST_KEYWORDS)
            has_detail_in_title = any(k in title_lower for k in DETAIL_KEYWORDS)
            if not (has_must_in_title and has_detail_in_title):
                continue

        authors_raw = item.get('author', [])
        authors_str = ', '.join(
            (a.get('given','') + ' ' + a.get('family','')).strip()
            for a in authors_raw[:3]
        ) + (' et al.' if len(authors_raw) > 3 else '')

        pub      = item.get('published', {}).get('date-parts', [['']])[0]
        date_str = '-'.join(str(x).zfill(2) for x in pub if x) or ''
        journal  = item.get('container-title', [''])[0]
        url      = item.get('URL', '#')

        seen_titles.add(title)
        crossref_papers.append({
            'title':    title,
            'authors':  authors_str,
            'date':     date_str,
            'url':      url,
            'abstract': abstract_clean[:200] + '...' if abstract_clean.strip() else '',
            'source':   'CrossRef (' + journal + ')' if journal else 'CrossRef',
        })

    print(f'  CrossRef {len(crossref_papers)}건 수집')

except Exception as e:
    print(f'  CrossRef 실패: {e}')


# arXiv 상위 10건 + CrossRef 상위 20건 합치기
arxiv_papers.sort(key=lambda x: x['date'],    reverse=True)
crossref_papers.sort(key=lambda x: x['date'], reverse=True)

papers = arxiv_papers[:10] + crossref_papers[:20]  # CrossRef 10 → 20건으로 확대
papers.sort(key=lambda x: x['date'], reverse=True)

print(f'  arXiv 상위 10건 + CrossRef 상위 20건 = 총 {len(papers)}건')

# 30일 이내면 NEW
today = datetime.now().date()
for p in papers:
    try:
        pub_date    = datetime.strptime(p['date'][:10], '%Y-%m-%d').date()
        p['is_new'] = (today - pub_date).days <= 30
    except Exception:
        p['is_new'] = False

new_count = sum(1 for p in papers if p['is_new'])
print(f'신규 논문 (30일 이내): {new_count}건 / 전체: {len(papers)}건')

output = {
    'updated':   datetime.now().strftime('%Y-%m-%d %H:%M'),
    'source':    'arXiv + CrossRef',
    'new_count': new_count,
    'items':     papers,
}

with open('data/papers.json', 'w', encoding='utf-8') as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print('data/papers.json 저장 완료!')
