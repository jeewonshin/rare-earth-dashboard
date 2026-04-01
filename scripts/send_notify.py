import smtplib
import json
import os
import sys
import base64
from datetime import datetime, date, timedelta
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

print('알림 메일 발송 시작...')

GMAIL_USER    = os.environ.get('GMAIL_USER',    '')
GMAIL_PASS    = os.environ.get('GMAIL_PASS',    '')
NOTIFY_EMAIL  = os.environ.get('NOTIFY_EMAIL',  '')
NOTIFY_CC     = os.environ.get('NOTIFY_CC',     '')
DASHBOARD_URL = 'http://lgemagone.xyz'

def img_to_base64(path):
    try:
        with open(path, 'rb') as f:
            data = base64.b64encode(f.read()).decode('utf-8')
        return 'data:image/png;base64,' + data
    except Exception as e:
        print(f'이미지 로드 실패 ({path}): {e}')
        return ''

to_list = [e.strip() for e in NOTIFY_EMAIL.split(',') if e.strip()]
cc_list = [e.strip() for e in NOTIFY_CC.split(',')   if e.strip()]

today        = datetime.now().strftime('%Y-%m-%d')
is_wednesday = datetime.now().weekday() == 2
week_ago     = str(date.today() - timedelta(days=7))

# ── 가격 데이터 로드 ──────────────────────────────────────────────────────
metals = []
try:
    with open('data/prices.json', 'r', encoding='utf-8') as f:
        prices_data = json.load(f)
    metals = prices_data.get('metals', [])
    print(f'가격 데이터: {len(metals)}개 금속')
except Exception as e:
    print(f'prices.json 로드 실패: {e}')

# ── 논문 데이터 로드 (7일 이내 신규) ─────────────────────────────────────
new_papers = []
try:
    with open('data/papers.json', 'r', encoding='utf-8') as f:
        papers_data = json.load(f)
    new_papers = [
        p for p in papers_data.get('items', [])
        if p.get('is_new') and p.get('first_seen', '') >= week_ago
    ]
    print(f'새 논문 (7일 이내 신규): {len(new_papers)}건')
except Exception as e:
    print(f'papers.json 로드 실패: {e}')

# ── 특허 데이터 로드 (7일 이내) ───────────────────────────────────────────
new_patents = []
try:
    with open('data/patents.json', 'r', encoding='utf-8') as f:
        patents_data = json.load(f)
    new_patents = [
        p for p in patents_data.get('items', [])
        if p.get('app_date', '') >= week_ago
    ]
    print(f'새 특허 (7일 이내): {len(new_patents)}건')
except Exception as e:
    print(f'patents.json 로드 실패: {e}')

# ── 뉴스 데이터 로드 (first_seen 기준 7일 이내) ───────────────────────────
new_news = []
try:
    with open('data/news.json', 'r', encoding='utf-8') as f:
        news_raw = json.load(f)
    items = news_raw if isinstance(news_raw, list) else news_raw.get('items', news_raw)
    new_news = [
        n for n in items
        if n.get('first_seen', n.get('date', n.get('pub_date', ''))) >= week_ago
    ]
    new_news.sort(key=lambda x: x.get('date', x.get('pub_date', '')), reverse=True)
    print(f'최근 뉴스 (7일 이내): {len(new_news)}건')
except Exception as e:
    print(f'news.json 로드 실패: {e}')

# ── 3% 이상 등락 광물 체크 ────────────────────────────────────────────────
price_alerts = []
for m in metals:
    t       = m.get('today', {})
    chg_pct = t.get('change_pct', None)
    if chg_pct is not None and abs(chg_pct) >= 3.0:
        name  = m.get('name', '')
        arrow = '+' if chg_pct >= 0 else ''
        price_alerts.append('⚠️ ' + name + ' ' + arrow + str(round(chg_pct, 1)) + '%')

# ── 발송 조건 체크 ────────────────────────────────────────────────────────
if not is_wednesday and not price_alerts:
    print('수요일 아님 + 가격 급등락 없음 → 메일 발송 안 함')
    sys.exit(0)

# ── 제목 생성 ─────────────────────────────────────────────────────────────
news_cnt = str(len(new_news))
if is_wednesday and not price_alerts:
    subject = ('[희토류 대시보드] 주간 요약 ' + today +
               ' | 논문 ' + str(len(new_papers)) + '건 · 특허 ' + str(len(new_patents)) + '건 · 뉴스 ' + news_cnt + '건')
elif is_wednesday and price_alerts:
    subject = ('[희토류 대시보드] 주간 요약 ' + today +
               ' | ' + ' · '.join(price_alerts) +
               ' | 논문 ' + str(len(new_papers)) + '건 · 특허 ' + str(len(new_patents)) + '건 · 뉴스 ' + news_cnt + '건')
else:
    subject = '[희토류 대시보드] 가격 긴급 알림 ' + today + ' | ' + ' · '.join(price_alerts)

print('제목: ' + subject)

# ── 워드클라우드 이미지 Base64 로드 ──────────────────────────────────────
wc_ko_src = img_to_base64('assets/images/wc_news_ko.png')
wc_en_src = img_to_base64('assets/images/wc_news_en.png')

# ── HTML 본문 생성 ────────────────────────────────────────────────────────
html  = '<html><body style="font-family:Segoe UI,sans-serif;background:#f0f4f8;padding:20px">'
html += '<div style="max-width:700px;margin:0 auto;background:white;border-radius:14px;padding:28px;">'
html += '<h1 style="color:#1a365d;border-bottom:2px solid #ebf8ff;padding-bottom:12px">'
if is_wednesday:
    html += '&#x1F9F2; 희토류 기술 대시보드 주간 요약</h1>'
else:
    html += '&#x26A0;&#xFE0F; 희토류 가격 긴급 알림</h1>'
html += '<p style="color:#666;font-size:13px">' + today + ' 기준 업데이트 내용입니다.</p>'

# 가격 경고 배너
if price_alerts:
    html += '<div style="background:#fff5f5;border:1px solid #fc8181;border-radius:8px;padding:10px 14px;margin:12px 0">'
    html += '<strong style="color:#c53030">&#x26A0;&#xFE0F; 가격 급등락 알림</strong><br>'
    html += '<span style="color:#c53030">' + ' &nbsp;|&nbsp; '.join(price_alerts) + '</span>'
    html += '</div>'

# ── 가격 섹션 ─────────────────────────────────────────────────────────────
html += '<h2 style="color:#2b6cb0;margin-top:24px">&#x1F4B0; 희토류 가격 동향</h2>'
if metals:
    for m in metals:
        t       = m.get('today', {})
        name    = m.get('name', '')
        grade   = m.get('grade', '')
        value   = t.get('value', None)
        date_s  = t.get('date', '--')
        chg_val = t.get('change_val', None)
        chg_pct = t.get('change_pct', None)
        val_str = str(round(value, 2)) + ' USD/kg' if value is not None else 'N/A'
        if chg_val is not None:
            arrow   = '&#x25B2;' if chg_val >= 0 else '&#x25BC;'
            color   = '#c53030' if chg_val >= 0 else '#276749'
            chg_str = arrow + ' ' + str(abs(round(chg_val, 2))) + ' (' + str(abs(round(chg_pct, 2))) + '%)'
        else:
            color   = '#888'
            chg_str = '-'
        bg = '#fff5f5' if (chg_pct is not None and abs(chg_pct) >= 3.0) else '#ebf8ff'
        html += '<div style="border-left:4px solid #2b6cb0;padding:8px 12px;margin:8px 0;background:' + bg + '">'
        html += '<strong>' + name + '</strong>'
        html += '&nbsp;&nbsp;<span style="font-size:18px;font-weight:bold;color:#1a365d">' + val_str + '</span>'
        html += '<br><small style="color:#888">등급: ' + grade + ' | 기준일: ' + date_s + '</small>'
        html += '<br><span style="color:' + color + ';font-weight:bold">' + chg_str + '</span>'
        html += '</div>'
else:
    html += '<p style="color:#aaa">가격 데이터 없음</p>'

# ── 수요일 전용 섹션 ──────────────────────────────────────────────────────
if is_wednesday:

    # ── 논문 섹션 ─────────────────────────────────────────────────────────
    html += '<h2 style="color:#6b46c1;margin-top:24px">&#x1F4C4; 이번 주 새 논문 ' + str(len(new_papers)) + '건</h2>'
    if new_papers:
        for p in new_papers:
            html += '<div style="border-left:4px solid #6b46c1;padding:8px 12px;margin:8px 0;background:#faf5ff">'
            html += '<a href="' + p.get('url','#') + '" style="color:#2b6cb0;font-weight:bold;text-decoration:none">'
            html += p.get('title','제목 없음') + '</a>'
            html += '<br><small style="color:#777">' + p.get('authors','') + ' &middot; ' + p.get('date','') + ' &middot; ' + p.get('source','') + '</small>'
            html += '<br><small style="color:#999">' + p.get('abstract','')[:150] + '...</small>'
            html += '</div>'
    else:
        html += '<p style="color:#aaa">이번 주 새 논문 없음</p>'

    # ── 특허 섹션 ─────────────────────────────────────────────────────────
    html += '<h2 style="color:#c53030;margin-top:24px">&#x1F510; 이번 주 새 특허 ' + str(len(new_patents)) + '건</h2>'
    if new_patents:
        for p in new_patents:
            html += '<div style="border-left:4px solid #c53030;padding:8px 12px;margin:8px 0;background:#fff5f5">'
            html += '<a href="' + p.get('url','#') + '" style="color:#2b6cb0;font-weight:bold;text-decoration:none">'
            html += p.get('title','제목 없음') + '</a>'
            html += '<br><small style="color:#777">' + p.get('applicant','') + ' &middot; 출원일: ' + p.get('app_date','') + '</small>'
            html += '<br><small style="color:#999">' + p.get('abstract','')[:150] + '...</small>'
            html += '</div>'
    else:
        html += '<p style="color:#aaa">이번 주 새 특허 없음</p>'

    # ── 뉴스 섹션 (카테고리별) ────────────────────────────────────────────
    html += '<h2 style="color:#276749;margin-top:24px">&#x1F4F0; 이번 주 뉴스 동향 ' + str(len(new_news)) + '건</h2>'
    CAT_CONFIG = [
        ('NdFeB',           '#2b6cb0', '#ebf8ff', '🔵 NdFeB 소결자석'),
        ('MnBi',            '#6b46c1', '#faf5ff', '🟣 MnBi 자석'),
        ('NdFeB_Recycling', '#276749', '#f0fff4', '🟢 Recycling 재활용'),
        ('기타',             '#718096', '#f7fafc', '⚪ 희토류 일반'),
    ]
    if new_news:
        for cat_key, border_color, bg_color, cat_label in CAT_CONFIG:
            cat_news = [n for n in new_news if n.get('category','기타') == cat_key]
            if not cat_news:
                continue
            html += '<div style="margin-top:16px">'
            html += '<strong style="color:' + border_color + ';font-size:14px">' + cat_label + ' (' + str(len(cat_news)) + '건)</strong>'
            html += '</div>'
            ko_news = [n for n in cat_news if n.get('source_lang','') == 'ko']
            en_news = [n for n in cat_news if n.get('source_lang','') != 'ko']
            for lang_label, lang_news in [('🇰🇷 국내', ko_news), ('🌍 해외', en_news)]:
                if not lang_news:
                    continue
                html += '<div style="margin:6px 0 2px 0"><small style="color:#999;font-weight:bold">' + lang_label + '</small></div>'
                for n in lang_news:
                    title_n = n.get('title', '제목 없음')
                    url_n   = n.get('url', '#')
                    source  = n.get('source', '')
                    date_n  = n.get('date', n.get('pub_date', ''))
                    html += '<div style="border-left:3px solid ' + border_color + ';padding:6px 10px;margin:4px 0;background:' + bg_color + '">'
                    html += '<a href="' + url_n + '" style="color:#1a365d;font-weight:bold;text-decoration:none;font-size:13px">' + title_n + '</a>'
                    html += '<br><small style="color:#999">' + source + ' &middot; ' + date_n + '</small>'
                    html += '</div>'
    else:
        html += '<p style="color:#aaa">이번 주 뉴스 없음</p>'

    # ── 워드클라우드 섹션 (Base64 임베드) ────────────────────────────────
    html += '<h2 style="color:#2b6cb0;margin-top:24px">&#x1F511; 키워드 트렌드 (워드클라우드)</h2>'
    html += '<div style="display:flex;gap:12px;flex-wrap:wrap;margin-top:8px">'
    html += '<div style="flex:1;min-width:280px">'
    html += '<p style="color:#666;font-size:12px;margin:0 0 4px 0">&#x1F1F0;&#x1F1F7; 국내 뉴스 키워드</p>'
    if wc_ko_src:
        html += '<img src="' + wc_ko_src + '" style="width:100%;border-radius:8px;border:1px solid #e2e8f0" />'
    else:
        html += '<p style="color:#aaa;font-size:12px;padding:20px;text-align:center;border:1px solid #e2e8f0;border-radius:8px">이미지 없음 (워드클라우드 먼저 실행)</p>'
    html += '</div>'
    html += '<div style="flex:1;min-width:280px">'
    html += '<p style="color:#666;font-size:12px;margin:0 0 4px 0">&#x1F30D; 해외 뉴스 키워드</p>'
    if wc_en_src:
        html += '<img src="' + wc_en_src + '" style="width:100%;border-radius:8px;border:1px solid #e2e8f0" />'
    else:
        html += '<p style="color:#aaa;font-size:12px;padding:20px;text-align:center;border:1px solid #e2e8f0;border-radius:8px">이미지 없음 (워드클라우드 먼저 실행)</p>'
    html += '</div>'
    html += '</div>'

# ── 바로가기 버튼 ─────────────────────────────────────────────────────────
html += '<div style="margin-top:24px;text-align:center">'
html += '<a href="' + DASHBOARD_URL + '" style="background:#2b6cb0;color:white;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:bold">'
html += '&#x1F449; 대시보드 바로가기</a>'
html += '</div>'
html += '<p style="color:#bbb;font-size:11px;text-align:right;margin-top:20px">자동 발송 &middot; 희토류 기술 대시보드</p>'
html += '</div></body></html>'

# ── 메일 구성 ─────────────────────────────────────────────────────────────
msg = MIMEMultipart('alternative')
msg['Subject'] = subject
msg['From']    = GMAIL_USER
msg['To']      = ', '.join(to_list)
if cc_list:
    msg['Cc']  = ', '.join(cc_list)
msg.attach(MIMEText(html, 'html', 'utf-8'))

all_recipients = to_list + cc_list

# ── Gmail SMTP 발송 ───────────────────────────────────────────────────────
try:
    with smtplib.SMTP('smtp.gmail.com', 587) as server:
        server.ehlo()
        server.starttls()
        server.login(GMAIL_USER, GMAIL_PASS)
        server.sendmail(GMAIL_USER, all_recipients, msg.as_string())
    print('메일 발송 완료!')
    print('수신: ' + ', '.join(to_list))
    if cc_list:
        print('참조: ' + ', '.join(cc_list))
except Exception as e:
    print(f'메일 발송 실패: {e}')
    sys.exit(1)
