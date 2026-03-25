import requests
import json
import os
import re
from datetime import datetime
from xml.etree import ElementTree as ET

print("KIPRIS 특허 수집 중...")

os.makedirs("data", exist_ok=True)

API_KEY = os.environ.get("KIPRIS_API_KEY", "")
BASE_URL = "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getWordSearch"

SEARCH_QUERIES = [
    "열간변형 영구자석 네오디뮴",
    "열간변형 영구자석 Nd-Fe-B",
    "열간변형 영구자석 세륨",
    "열간변형 영구자석 입계확산",
    "열간변형 영구자석 Ce 치환",
    "hot deformation permanent magnet NdFeB",
    "hot deformation permanent magnet Nd-Fe-B",
    "hot deformation permanent magnet Ce substituted",
    "hot deformation permanent magnet grain boundary diffusion",
    "hot deformed permanent magnet rare earth",
]

MUST_ALL_KO = ["열간변형", "영구자석"]
MUST_ALL_EN = ["hot deform", "permanent magnet"]

DETAIL_ANY = [
    "nd-fe-b", "ndfeb", "네오디뮴", "neodymium",
    "세륨", "ce 치환", "ce-치환", "cerium", "ce substitut",
    "입계확산", "입계 확산", "grain boundary",
    "희토류", "rare earth",
]

patents = []
seen_ids = set()


def fmt_date(d):
    d = re.sub(r"[^0-9]", "", d)
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d


for query in SEARCH_QUERIES:
    print(f"  검색어: {query}")
    try:
        params = {
            "word": query,
            "ServiceKey": API_KEY,
            "docsStart": 1,
            "docsCount": 10,
            "patent": "true",
            "utility": "false",
            "sortSpec": "AD",
            "descSort": "true",
        }

        res = requests.get(BASE_URL, params=params, timeout=20)
        res.raise_for_status()

        root = ET.fromstring(res.text)
        err_msg = root.findtext(".//errMsg", "")
        if err_msg:
            print(f"  API 오류: {err_msg}")
            continue

        count = root.findtext(".//totalCount", "0")
        print(f"  검색 결과: {count}건")

        for item in root.findall(".//item"):
            app_no = item.findtext("applicationNumber", "").strip()
            if not app_no or app_no in seen_ids:
                continue

            title = item.findtext("inventionTitle", "제목 없음").strip()
            app_date = item.findtext("applicationDate", "").strip()
            applicant = item.findtext("applicantName", "출원인 미상").strip()
            ipc = item.findtext("ipcNumber", "").strip()
            abstract = item.findtext("astrtCont", "").strip()

            text_lower = (title + " " + abstract).lower()
            has_must_ko = all(k.lower() in text_lower for k in MUST_ALL_KO)
            has_must_en = all(k.lower() in text_lower for k in MUST_ALL_EN)
            has_must = has_must_ko or has_must_en
            has_detail = any(k.lower() in text_lower for k in DETAIL_ANY)

            if not has_must:
                print(f"    필수 키워드 없음: {title[:40]}...")
                continue
            if not has_detail:
                print(f"    세부 키워드 없음: {title[:40]}...")
                continue

            app_date_fmt = fmt_date(app_date)

            try:
                app_dt = datetime.strptime(app_date_fmt[:10], "%Y-%m-%d").date()
                days_old = (datetime.now().date() - app_dt).days
                if days_old > 365 * 5:
                    print(f"    날짜 초과 ({app_date_fmt}): {title[:40]}...")
                    continue
            except Exception:
                pass

            url = f"https://plus.kipris.or.kr/kipi/patinfo/view.do?applicationNumber={app_no}"

            seen_ids.add(app_no)
            patents.append({
                "title": title,
                "app_no": app_no,
                "applicant": applicant,
                "app_date": app_date_fmt,
                "ipc": ipc,
                "url": url,
                "abstract": abstract[:200] + "..." if len(abstract) > 200 else abstract,
                "source": "KIPRIS",
            })
            print(f"  추가: {title[:50]}...")

    except Exception as e:
        print(f"  실패: {e}")


patents.sort(key=lambda x: x["app_date"], reverse=True)
patents = patents[:20]

today = datetime.now().date()
for p in patents:
    try:
        app_date = datetime.strptime(p["app_date"][:10], "%Y-%m-%d").date()
        p["is_new"] = (today - app_date).days <= 30
    except Exception:
        p["is_new"] = False

new_count = sum(1 for p in patents if p["is_new"])
print(f"신규 특허 (30일 이내): {new_count}건 / 전체: {len(patents)}건")

output = {
    "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "source": "KIPRIS (한국특허정보원)",
    "source_url": "https://plus.kipris.or.kr",
    "new_count": new_count,
    "items": patents,
}

with open("data/patents.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"data/patents.json 저장 완료! ({len(patents)}건)")
