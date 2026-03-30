import requests
import json
import os
import re
from datetime import datetime
from xml.etree import ElementTree as ET

print("KIPRIS 특허 수집 중 (카테고리별 독립 수집)...")

os.makedirs("data", exist_ok=True)

# ── 카테고리 정의 ─────────────────────────────────────────────────────────
CATEGORIES = {
    "NdFeB": [
        "Nd-Fe-B", "NdFeB", "neodymium iron boron", "neodymium magnet",
        "sintered magnet", "hot deformation", "hot deform", "hot press",
        "grain boundary diffusion", "HPMS", "Ce substitution", "Ce substitut",
        "Dy substitution", "coercivity", "permanent magnet",
        "네오디뮴", "소결자석", "열간변형", "열간성형", "입계확산", "영구자석"
    ],
    "MnBi": [
        "MnBi", "manganese bismuth", "MnBi magnet",
        "hard magnetic MnBi", "low temperature phase MnBi", "LTP-MnBi",
        "망간비스무스", "망간 비스무트"
    ],
    "NdFeB_Recycling": [
        "NdFeB recycling", "NdFeB recycle", "rare earth recycling",
        "magnet recycling", "hydrogen decrepitation",
        "rare earth recovery", "end-of-life magnet", "urban mining",
        "재활용", "회수", "재생", "수소분쇄"
    ],
}


def classify_category(title, abstract=""):
    """통계/검증용 카테고리 분류"""
    text = (title + " " + abstract).lower()
    scores = {cat: 0 for cat in CATEGORIES}
    for cat, keywords in CATEGORIES.items():
        for kw in keywords:
            if kw.lower() in text:
                scores[cat] += 1
    best = max(scores, key=scores.get)
    return best if scores[best] > 0 else "기타"


# ── 카테고리별 수집 설정 ───────────────────────────────────────────────────
CATEGORY_CONFIGS = [
    {
        "category": "NdFeB",
        "queries": [
            "영구자석 네오디뮴",
            "영구자석 Nd",
            "영구자석 열간",
            "영구자석 입계확산",
            "permanent magnet NdFeB",
            "permanent magnet hot deform",
            "permanent magnet grain boundary",
        ],
        # 조건1: 제목에 하나라도
        "must_title":  ["자석", "permanent magnet"],
        # 조건2: 제목+초록에 하나라도
        "must_nd":     ["ndfeb", "nd-fe-b", "네오디뮴", "neodymium"],
        # 조건3: 제목+초록에 하나라도
        "detail_any":  [
            "열간변형", "열간성형", "열간가압", "열간소성",
            "열간 변형", "열간 성형", "열간 가압",
            "치환", "세륨", "cerium", "ce substitut",
            "입계확산", "입계 확산", "grain boundary",
            "hot deform", "hot press",
            "희토류", "rare earth",
        ],
        "max_results": 20,
    },
    {
        "category": "MnBi",
        "queries": [
            "망간비스무트 자석",
            "망간비스무스 자석",
            "MnBi 자석",
            "비스무트 자석",
            "MnBi magnet",
            "bismuth manganese magnet",
            "망간 비스무트 분말",
        ],
        # 조건1: 제목+초록에 하나라도
        "must_mnbi":   ["mnbi", "mn-bi", "망간비스무트", "망간비스무스",
                        "비스무트", "비스무스", "bismuth", "manganese"],
        # 조건2: 제목+초록에 하나라도
        "must_magnet": ["자석", "magnet", "분말", "powder", "경자성"],
        "max_results": 15,
    },
    {
        "category": "NdFeB_Recycling",
        "queries": [
            "희토류 재활용 자석",
            "영구자석 재활용",
            "자석 재생",
            "희토류 회수",
            "수소분쇄 자석",
            "magnet recycling rare earth",
            "rare earth recovery magnet",
        ],
        # 조건1: 제목+초록에 하나라도
        "must_recycle": ["재활용", "재생", "회수", "수소분쇄",
                         "hydrogen decrepitation", "magnet recycling",
                         "rare earth recycling"],
        # 조건2: 제목+초록에 하나라도
        "must_magnet":  ["자석", "magnet", "희토류", "rare earth", "네오디뮴"],
        "max_results": 15,
    },
]

API_KEY  = os.environ.get("KIPRIS_API_KEY", "")
BASE_URL = "http://plus.kipris.or.kr/kipo-api/kipi/patUtiModInfoSearchSevice/getWordSearch"


def fmt_date(d):
    d = re.sub(r"[^0-9]", "", d)
    return f"{d[:4]}-{d[4:6]}-{d[6:]}" if len(d) == 8 else d


def passes_filter(cfg, title, abstract):
    """카테고리별 필터 조건 적용"""
    title_lower = title.lower()
    text_lower  = (title + " " + abstract).lower()
    cat = cfg["category"]

    if cat == "NdFeB":
        has_title  = any(k.lower() in title_lower for k in cfg["must_title"])
        has_nd     = any(k.lower() in text_lower  for k in cfg["must_nd"])
        has_detail = any(k.lower() in text_lower  for k in cfg["detail_any"])
        if not has_title:
            return False, "조건1 탈락: 제목에 자석 없음"
        if not has_nd:
            return False, "조건2 탈락: NdFeB/네오디뮴 없음"
        if not has_detail:
            return False, "조건3 탈락: 세부 키워드 없음"
        return True, "통과"

    elif cat == "MnBi":
        has_mnbi   = any(k.lower() in text_lower for k in cfg["must_mnbi"])
        has_magnet = any(k.lower() in text_lower for k in cfg["must_magnet"])
        if not has_mnbi:
            return False, "조건1 탈락: MnBi/비스무트 없음"
        if not has_magnet:
            return False, "조건2 탈락: 자석/분말/경자성 없음"
        return True, "통과"

    elif cat == "NdFeB_Recycling":
        has_recycle = any(k.lower() in text_lower for k in cfg["must_recycle"])
        has_magnet  = any(k.lower() in text_lower for k in cfg["must_magnet"])
        if not has_recycle:
            return False, "조건1 탈락: 재활용/회수 없음"
        if not has_magnet:
            return False, "조건2 탈락: 자석/희토류 없음"
        return True, "통과"

    return False, "알 수 없는 카테고리"


# ── 카테고리별 수집 ───────────────────────────────────────────────────────
all_patents = []
seen_ids    = set()   # 전체 공유 - 카테고리 간 중복 제거

for cfg in CATEGORY_CONFIGS:
    cat          = cfg["category"]
    cat_patents  = []

    print(f"\n  ── [{cat}] 수집 중 ──")

    for query in cfg["queries"]:
        if len(cat_patents) >= cfg["max_results"]:
            break

        print(f"    검색어: {query}")
        try:
            params = {
                "word":       query,
                "ServiceKey": API_KEY,
                "docsStart":  1,
                "docsCount":  50,
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
                print(f"    API 오류: {err_msg}")
                continue

            count = root.findtext(".//totalCount", "0")
            print(f"    검색 결과: {count}건")

            for item in root.findall(".//item"):
                if len(cat_patents) >= cfg["max_results"]:
                    break

                app_no = item.findtext("applicationNumber", "").strip()
                if not app_no or app_no in seen_ids:
                    continue

                title     = item.findtext("inventionTitle",  "제목 없음").strip()
                app_date  = item.findtext("applicationDate", "").strip()
                applicant = item.findtext("applicantName",   "출원인 미상").strip()
                ipc       = item.findtext("ipcNumber",       "").strip()
                abstract  = item.findtext("astrtCont",       "").strip()

                # 필터 적용
                ok, reason = passes_filter(cfg, title, abstract)
                if not ok:
                    print(f"      [{reason}] {title[:40]}...")
                    continue

                app_date_fmt = fmt_date(app_date)

                # 10년 날짜 필터
                try:
                    app_dt   = datetime.strptime(app_date_fmt[:10], "%Y-%m-%d").date()
                    days_old = (datetime.now().date() - app_dt).days
                    if days_old > 365 * 10:
                        print(f"      [날짜 초과] ({app_date_fmt}): {title[:40]}...")
                        continue
                except Exception:
                    pass

                app_no_clean = re.sub(r"[^0-9]", "", app_no)
                url = f"https://doi.org/10.8080/{app_no_clean}"

                seen_ids.add(app_no)
                cat_patents.append({
                    "title":     title,
                    "app_no":    app_no,
                    "applicant": applicant,
                    "app_date":  app_date_fmt,
                    "ipc":       ipc,
                    "url":       url,
                    "abstract":  abstract[:200] + "..." if len(abstract) > 200 else abstract,
                    "source":    "KIPRIS",
                    "category":  cat,   # 강제 할당
                })
                print(f"      ✅ {title[:50]}...")

        except Exception as e:
            print(f"    실패: {e}")

    print(f"  [{cat}] 총 {len(cat_patents)}건 수집")
    all_patents.extend(cat_patents)


# ── 정렬 및 is_new 처리 ───────────────────────────────────────────────────
all_patents.sort(key=lambda x: x["app_date"], reverse=True)

today = datetime.now().date()
for p in all_patents:
    try:
        app_date    = datetime.strptime(p["app_date"][:10], "%Y-%m-%d").date()
        p["is_new"] = (today - app_date).days <= 30
    except Exception:
        p["is_new"] = False

new_count = sum(1 for p in all_patents if p["is_new"])
print(f"\n신규 특허 (30일 이내): {new_count}건 / 전체: {len(all_patents)}건")

# ── 카테고리별 통계 출력 ───────────────────────────────────────────────────
cat_counts = {}
for p in all_patents:
    cat = p.get("category", "기타")
    cat_counts[cat] = cat_counts.get(cat, 0) + 1
for cat, cnt in cat_counts.items():
    print(f"  [{cat}] {cnt}건")

output = {
    "updated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    "source":     "KIPRIS (한국특허정보원)",
    "source_url": "https://plus.kipris.or.kr",
    "new_count":  new_count,
    "categories": list(CATEGORIES.keys()),
    "items":      all_patents,
}

with open("data/patents.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"data/patents.json 저장 완료! ({len(all_patents)}건)")
