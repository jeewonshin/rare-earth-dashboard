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

# ── 검색 쿼리 ─────────────────────────────────────────────
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

# ── 검색 쿼리 ─────────────────────────────────────────────
SEARCH_QUERIES = [
    # 한국어 쿼리
    "열간변형 영구자석 네오디뮴",
    "열간변형 영구자석 Nd-Fe-B",
    "열간변형 영구자석 세륨",
    "열간변형 영구자석 입계확산",
    "열간변형 영구자석 Ce 치환",
    # 영어 쿼리
    "hot deformation permanent magnet NdFeB",
    "hot deformation permanent magnet Nd-Fe-B",
    "hot deformation permanent magnet Ce substituted",
    "hot deformation permanent magnet grain boundary diffusion",
    "hot deformed permanent magnet rare earth",
]

# ── 필터링 키워드 ─────────────────────────────────────────
# 필수: 둘 다 포함되어야 함
MUST_ALL = [
    "열간변형",
    "영구자석",
]

# 세부: 하나 이상 포함되어야 함
DETAIL_ANY = [
    "nd-fe-b", "ndfeb", "네오디뮴",
    "세륨", "ce 치환", "ce-치환",
    "입계확산", "입계 확산",
    "grain boundary", "ce substitut",
    "hot deform", "permanent magnet",
    "희토류",
]

patents  = []
seen_ids = set()

for query in SEARCH_QUERIES:
    print(f"\n  검색어: {query}")
    try:
        params = {
            "word":       query,
            "ServiceKey": API_KEY,
            "docsStart":  1,
            "docsCount":  10,
            "patent":     "true",
            "utility":    "false",
            "sortSpec":   "AD",
            "descSort":   "true",
        }

        res = requests.get(BASE_URL, params=params, timeout=20)
        res.raise_for_status()

        root    = ET.fromstring(res.text)
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

            # ── 후처리 필터링 ─────────────────────────────
            text_lower = (title + " " + abstract).lower()

            # 필수 키워드 둘 다 있어야 함
            has_must = all(k.lower() in text_lower for k in MUST_ALL)

            # 세부 키워드 하나 이상 있어야 함
            has_detail = any(k.lower() in text_lower for k in DETAIL_ANY)

            if not has_must:
                print(f"    ⏭ 필수 키워드 없음: {title[:40]}...")
                continue
            if not has_detail:
                print(f"    ⏭ 세부 키워드 없음: {title[:40]}...")
                continue

            # ── 날짜 포맷 (20240101 → 2024-01-01) ────────
            def fmt_date(d):
                d = re.sub(r"[^0-9]", "", d)
                return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d

            app_date_fmt = fmt_date(app_date)

            # ── 날짜 필터: 최근 1년 이내만 ───────────────
            try:
                app_dt   = datetime.strptime(app_date_fmt[:10], "%Y-%m-%d").date()
                days_old = (datetime.now().date() - app_dt).days
                if days_old > 365:
                    print(f"    ⏭ 날짜 초과 ({app_date_fmt}): {title[:40]}...")
                    continue
            except:
                pass

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
patents = patents[:20]

# ── 출원일 기준 30일 이내면 NEW ───────────────────────────
today = datetime.now().date()

for p in patents:
    try:
        app_date    = datetime.strptime(p["app_date"][:10], "%Y-%m-%d").date()
        p["is_new"] = (today - app_date).days <= 30
    except:
        p["is_new"] = False

new_count = sum(1 for p in patents if p["is_new"])
print(f"\n신규 특허 (30일 이내): {new_count}건 / 전체: {len(patents)}건")

for p in patents[:5]:
    print(f"  {p['app_date']} | {p['title'][:50]}...")

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

# ── 필터링 키워드 ─────────────────────────────────────────
# 필수: 둘 다 포함되어야 함
MUST_ALL = [
    "열간변형",
    "영구자석",
]

# 세부: 하나 이상 포함되어야 함
DETAIL_ANY = [
    "nd-fe-b", "ndfeb", "네오디뮴",
    "세륨", "ce 치환", "ce-치환",
    "입계확산", "입계 확산",
    "grain boundary", "ce substitut",
    "hot deform", "permanent magnet",
    "희토류",
]

patents  = []
seen_ids = set()

for query in SEARCH_QUERIES:
    print(f"\n  검색어: {query}")
    try:
        params = {
            "word":       query,
            "ServiceKey": API_KEY,
            "docsStart":  1,
            "docsCount":  10,
            "patent":     "true",
            "utility":    "false",
            "sortSpec":   "AD",
            "descSort":   "true",
        }

        res = requests.get(BASE_URL, params=params, timeout=20)
        res.raise_for_status()

        root    = ET.fromstring(res.text)
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

            # ── 후처리 필터링 ─────────────────────────────
            text_lower = (title + " " + abstract).lower()

            # 필수 키워드 둘 다 있어야 함
            has_must = all(k.lower() in text_lower for k in MUST_ALL)

            # 세부 키워드 하나 이상 있어야 함
            has_detail = any(k.lower() in text_lower for k in DETAIL_ANY)

            if not has_must:
                print(f"    ⏭ 필수 키워드 없음: {title[:40]}...")
                continue
            if not has_detail:
                print(f"    ⏭ 세부 키워드 없음: {title[:40]}...")
                continue

            # ── 날짜 포맷 (20240101 → 2024-01-01) ────────
            def fmt_date(d):
                d = re.sub(r"[^0-9]", "", d)
                return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d

            app_date_fmt = fmt_date(app_date)

            # ── 날짜 필터: 최근 1년 이내만 ───────────────
            try:
                app_dt   = datetime.strptime(app_date_fmt[:10], "%Y-%m-%d").date()
                days_old = (datetime.now().date() - app_dt).days
                if days_old > 365:
                    print(f"    ⏭ 날짜 초과 ({app_date_fmt}): {title[:40]}...")
                    continue
            except:
                pass

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
patents = patents[:20]

# ── 출원일 기준 30일 이내면 NEW ───────────────────────────
today = datetime.now().date()

for p in patents:
    try:
        app_date    = datetime.strptime(p["app_date"][:10], "%Y-%m-%d").date()
        p["is_new"] = (today - app_date).days <= 30
    except:
        p["is_new"] = False

new_count = sum(1 for p in patents if p["is_new"])
print(f"\n신규 특허 (30일 이내): {new_count}건 / 전체: {len(patents)}건")

for p in patents[:5]:
    print(f"  {p['app_date']} | {p['title'][:50]}...")

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
