import smtplib
import json
import os
import sys
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

print('알림 메일 발송 시작...')

GMAIL_USER    = os.environ.get('GMAIL_USER',    '')
GMAIL_PASS    = os.environ.get('GMAIL_PASS',    '')
NOTIFY_EMAIL  = os.environ.get('NOTIFY_EMAIL',  '')
NOTIFY_CC     = os.environ.get('NOTIFY_CC',     '')
DASHBOARD_URL = 'http://lgemagone.xyz'

to_list = [e.strip() for e in NOTIFY_EMAIL.split(',') if e.strip()]
cc_list = [e.strip() for e in NOTIFY_CC.split(',')   if e.strip()]

today        = datetime.now().strftime('%Y-%m-%d')
is_wednesday = datetime.now().weekday() == 2

# 가격 데이터 로드
metals = []
try:
    with open('data/prices.json', 'r', encoding='utf-8') as f:
        prices_data = json.load(f)
    metals = prices_data.get('metals', [])
    print(f'가격 데이터: {len(metals)}개 금속')
except Exception as e:
    print(f'prices.json 로드 실패: {e}')

# 논문 데이터 로드
new_papers = []
try:
    with open('data/papers.json', 'r', encoding='utf-8') as f:
        papers_data = json.load(f)
    new_papers = [p for p in papers_data.get('items', []) if p.get('is_new')]
    print(f'새 논문: {len(new_papers)}건')
except Exception as e:
    print(f'papers.json 로드 실패: {e}')

# 특허 데이터 로드
new_patents = []
try:
    with open('data/patents.json', 'r', encoding='utf-8') as f:
        patents_data = json.load(f)
    new_patents = [p for p in patents_data.get('items', []) if p.get('is_new')]
    print(f'새 특허: {len(new_patents)}건')
except Exception as e:
    print(f'patents.json 로드 실패: {e}')

# 3% 이상 등락 광물 체크
price_alerts = []
for m in metals:
    t       = m.get('today', {})
    chg_pct = t.get('change_pct', None)
    if chg_pct is not None and abs(chg_pct) >= 3.0:
        name  = m.get('name', '')
        arrow = '+' if chg_pct >= 0 else ''
        price_alerts.append('⚠️ ' + name + ' ' + arrow + str(round(chg_pct, 1)) + '%')

# 발송 조건 체크
if not is_wednesday and not price_alerts:
    print('수요일 아님 + 가격 급등락 없음 → 메일 발송 안 함')
    sys.exit(0)

# 제목 생성
if is_wednesday and not price_alerts:
    subject = '[희토류 대시보드] 주간 요약 ' + today + ' | 논문 ' + str(len(new_papers)) + '건 · 특허 ' + str(len(new_patents)) + '건'
elif is_wednesday and price_alerts:
    subject = '[희토류 대시보드] 주간 요약 ' + today + ' | ' + ' · '.join(price_alerts) + ' | 논문 ' + str(len(new_papers)) + '건 · 특허 ' + str(len(new_patents)) + '건'
else:
    subject = '[희토류 대시보드] 가격 긴급 알림 ' + today + ' | ' + ' · '.join(price_alerts)

print('제목: ' + subject)

# HTML 본문 생성
html = '<html><body style="font-family:Segoe UI,sans-serif;background:#f0f4f8;padding:20px">'
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

# 가격 섹션 (항상 표시)
html += '<h2 style="color:#2b6cb0;margin-top:24px">&#x1F4B0; 희토류 가격 동향</h2>'
if metals:
    for m in metals:
        t       = m.get('today', {})
        name    = m.get('name', '')
        grade   = m.get('grade', '')
        value   = t.get('value', None)
        date    = t.get('date', '--')
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
        html += '<br><small style="color:#888">등급: ' + grade + ' | 기준일: ' + date + '</small>'
        html += '<br><span style="color:' + color + ';font-weight:bold">' + chg_str + '</span>'
        html += '</div>'
else:
    html += '<p style="color:#aaa">가격 데이터 없음</p>'

# 논문/특허 섹션 (수요일만)
if is_wednesday:
    html += '<h2 style="color:#6b46c1;margin-top:24px">&#x1F4C4; 새 논문 ' + str(len(new_papers)) + '건</h2>'
    if new_papers:
        for p in new_papers:
            html += '<div style="border-left:4px solid #6b46c1;padding:8px 12px;margin:8px 0;background:#faf5ff">'
            html += '<a href="' + p.get('url','#') + '" style="color:#2b6cb0;font-weight:bold;text-decoration:none">'
            html += p.get('title','제목 없음') + '</a>'
            html += '<br><small style="color:#777">' + p.get('authors','') + ' &middot; ' + p.get('date','') + ' &middot; ' + p.get('source','') + '</small>'
            html += '<br><small style="color:#999">' + p.get('abstract','')[:150] + '...</small>'
            html += '</div>'
    else:
        html += '<p style="color:#aaa">이번 달 새 논문 없음</p>'

    html += '<h2 style="color:#c53030;margin-top:24px">&#x1F510; 새 특허 ' + str(len(new_patents)) + '건</h2>'
    if new_patents:
        for p in new_patents:
            html += '<div style="border-left:4px solid #c53030;padding:8px 12px;margin:8px 0;background:#fff5f5">'
            html += '<a href="' + p.get('url','#') + '" style="color:#2b6cb0;font-weight:bold;text-decoration:none">'
            html += p.get('title','제목 없음') + '</a>'
            html += '<br><small style="color:#777">' + p.get('applicant','') + ' &middot; 출원일: ' + p.get('app_date','') + '</small>'
            html += '<br><small style="color:#999">' + p.get('abstract','')[:150] + '...</small>'
            html += '</div>'
    else:
        html += '<p style="color:#aaa">이번 달 새 특허 없음</p>'

# 바로가기 버튼
html += '<div style="margin-top:24px;text-align:center">'
html += '<a href="' + DASHBOARD_URL + '" style="background:#2b6cb0;color:white;padding:10px 24px;border-radius:8px;text-decoration:none;font-weight:bold">'
html += '&#x1F449; 대시보드 바로가기</a>'
html += '</div>'
html += '<p style="color:#bbb;font-size:11px;text-align:right;margin-top:20px">자동 발송 &middot; 희토류 기술 대시보드</p>'
html += '</div></body></html>'

# 메일 구성
msg = MIMEMultipart('alternative')
msg['Subject'] = subject
msg['From']    = GMAIL_USER
msg['To']      = ', '.join(to_list)
if cc_list:
    msg['Cc']  = ', '.join(cc_list)
msg.attach(MIMEText(html, 'html', 'utf-8'))

all_recipients = to_list + cc_list

# Gmail SMTP 발송
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
