import requests
import json
import os
import re
from datetime import datetime, timedelta
from xml.etree import ElementTree as ET

print("📡 KIPRIS 특허 수집 중...")

os.makedirs("data", exist_ok=True)

API_KEY  = os.environ.get("KIPRIS_API_KEY", "")
BASE_URL = "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getWordSearch"

# ── 키워드 구조 ───────────────────────────────────────────
# 필수: permanent magnet OR Nd-Fe-B
# 세부: Hot deform OR Ce substituted OR Grain boundary diffusion

SEARCH_QUERIES = [
    "permanent magnet Hot deformation",
    "permanent magnet Ce substituted",
    "permanent magnet Grain boundary diffusion",
    "Nd-Fe-B Hot deformation",
    "Nd-Fe-B Ce substituted",
    "Nd-Fe-B Grain boundary diffusion",
]

# 후처리 필터링용
MUST_KEYWORDS   = ["permanent magnet", "nd-fe-b", "ndfeb"]
DETAIL_KEYWORDS = ["hot deform", "ce substitut", "grain boundary diffusion"]

patents  = []
seen_ids = set()

for query in SEARCH_QUERIES:
    print(f"\n  검색어: {query}")
    try:
        params = {
            "word":       query,
            "ServiceKey": API_KEY,
            "docsStart":  1,
            "docsCount":  5,
            "patent":     "true",
            "utility":    "false",
            "sortSpec":   "AD",      # 출원일 기준
            "descSort":   "true",    # 최신순
        }

        res = requests.get(BASE_URL, params=params, timeout=20)
        res.raise_for_status()

        print(f"  응답 코드: {res.status_code}")

        root  = ET.fromstring(res.text)

        # 오류 메시지 확인
        err_msg = root.findtext(".//errMsg", "")
        if err_msg:
            print(f"  ⚠️ API 오류: {err_msg}")
            continue

        count = root.findtext(".//totalCount", "0")
        print(f"  검색 결과: {count}건")

        for item in root.findall(".//item"):
            app_no = item.findtext("applicationNumber", "").strip()
            if not app_no or app_no in seen_ids:
                continue

            title     = item.findtext("inventionTitle",  "제목 없음").strip()
            app_date  = item.findtext("applicationDate", "").strip()
            applicant = item.findtext("applicantName",   "출원인 미상").strip()
            ipc       = item.findtext("ipcNumber",       "").strip()
            abstract  = item.findtext("astrtCont",       "").strip()

            # 후처리 필터링
            text_lower = (title + " " + abstract).lower()
            has_must   = any(k in text_lower for k in MUST_KEYWORDS)
            has_detail = any(k in text_lower for k in DETAIL_KEYWORDS)

            if not (has_must and has_detail):
                continue

            # 날짜 포맷 (20240101 → 2024-01-01)
            def fmt_date(d):
                d = re.sub(r"[^0-9]", "", d)
                return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d

            app_date_fmt = fmt_date(app_date)
            url = f"https://plus.kipris.or.kr/kipi/patinfo/view.do?applicationNumber={app_no}"

            seen_ids.add(app_no)
            patents.append({
                "title":     title,
                "app_no":    app_no,
                "applicant": applicant,
                "app_date":  app_date_fmt,
                "ipc":       ipc,
                "url":       url,
                "abstract":  abstract[:200] + "..." if len(abstract) > 200 else abstract,
                "source":    "KIPRIS",
            })
            print(f"  ✅ 추가: {title[:50]}...")

    except Exception as e:
        print(f"  ❌ 실패: {e}")
        import traceback; traceback.print_exc()

# ── 출원일 기준 최신순 정렬 ───────────────────────────────
patents.sort(key=lambda x: x["app_date"], reverse=True)
patents = patents[:15]

# ── 출원일 기준 7일 이내면 NEW ────────────────────────────
today = datetime.now().date()

for p in patents:
    try:
        app_date    = datetime.strptime(p["app_date"][:10], "%Y-%m-%d").date()
        p["is_new"] = (today - app_date).days <= 7
    except:
        p["is_new"] = False

new_count = sum(1 for p in patents if p["is_new"])
print(f"\n신규 특허 (7일 이내): {new_count}건 / 전체: {len(patents)}건")

output = {
    "updated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    "source":     "KIPRIS (한국특허정보원)",
    "source_url": "https://plus.kipris.or.kr",
    "new_count":  new_count,
    "items":      patents,
}

with open("data/patents.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ data/patents.json 저장 완료! ({len(patents)}건)")
