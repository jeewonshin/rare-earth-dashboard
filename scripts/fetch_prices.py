import requests
import json
import os
from datetime import datetime

print("📡 KOMIS 네오디뮴 차트+가격 수집 중...")

URL = "https://www.komis.or.kr/Komis/RsrcPrice/ajax/getChartData"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

PARAMS = {
    "mnrkndUnqRadioCd":       "MNRL1001",
    "srchMnrkndUnqCd":        "MNRL1001",
    "srchPrcCrtr":            "757",
    "spcfct":                 "99.5",
    "srchAvgOpt":             "DAY",
    "srchField":              "year",
    "srchStartDate":          "2024",
    "srchEndDate":            str(datetime.now().year),
    "srchCompareMnrkndUnqCd": "",
    "srchComparePrcCrtr":     "",
    "lmeInvt":                "Y",
    "HP000":                  "HP002",
}

os.makedirs("data", exist_ok=True)

try:
    res = requests.post(URL, data=PARAMS, headers=HEADERS, timeout=20)
    res.raise_for_status()
    raw = res.json()

    # ── 구조 확인용 전체 키 출력 ──────────────────────────
    print("최상위 키:", list(raw.keys()))
    print("data 키:", list(raw["data"].keys()))

    # ── xaxis / yaxis 파싱 ────────────────────────────────
    xaxis = raw["data"]["xaxis"]   # 날짜 리스트
    
    # yaxis 키 이름 확인 (yaxis, yData, series 등 가능)
    data_section = raw["data"]
    y_key = None
    for k in data_section.keys():
        if k != "xaxis":
            print(f"  후보 키: {k} → {str(data_section[k])[:80]}")
            if isinstance(data_section[k], list) and len(data_section[k]) == len(xaxis):
                y_key = k
                print(f"  ✅ yaxis 키 발견: {k}")
                break

    if y_key is None:
        # yaxis가 중첩 구조인 경우 (예: series[0].data)
        for k in data_section.keys():
            val = data_section[k]
            if isinstance(val, list) and len(val) > 0 and isinstance(val[0], dict):
                inner = val[0].get("data", val[0].get("values", None))
                if inner and len(inner) == len(xaxis):
                    y_key  = k
                    xaxis  = xaxis
                    yaxis  = inner
                    print(f"  ✅ 중첩 yaxis 키 발견: {k}[0].data")
                    break
        else:
            yaxis = []
    else:
        yaxis = data_section[y_key]

    print(f"\n날짜 {len(xaxis)}건, 가격 {len(yaxis)}건")

    # ── history 조합 ──────────────────────────────────────
    history = []
    for d, v in zip(xaxis, yaxis):
        try:
            if v is not None and v != "" and v != "-":
                history.append({
                    "date":  str(d).strip(),
                    "value": float(v)
                })
        except:
            pass

    print(f"히스토리 파싱 건수: {len(history)}")

    # ── 오늘 가격 / 등락 계산 ────────────────────────────
    today_price = today_date = change_val = change_pct = None

    if history:
        latest      = history[-1]
        today_price = latest["value"]
        today_date  = latest["date"]

        if len(history) >= 2:
            prev       = history[-2]["value"]
            change_val = round(today_price - prev, 4)
            change_pct = round((change_val / prev) * 100, 2) if prev else 0

    print(f"\n📊 최종 결과:")
    print(f"  오늘 날짜 : {today_date}")
    print(f"  오늘 가격 : {today_price} USD/kg")
    print(f"  전일 등락 : {change_val} ({change_pct}%)")
    print(f"  히스토리  : {len(history)}건")

    output = {
        "updated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source":     "KOMIS (한국자원정보서비스)",
        "source_url": "https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals",
        "status":     "success",
        "today": {
            "date":       today_date or datetime.now().strftime("%Y-%m-%d"),
            "value":      today_price,
            "unit":       "USD/kg",
            "grade":      "99.5%min FOB China",
            "change_val": change_val,
            "change_pct": change_pct,
        },
        "history": history,
    }

except Exception as e:
    print(f"❌ 오류: {e}")
    import traceback; traceback.print_exc()
    output = {
        "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "source":  "KOMIS", "source_url": "",
        "status":  "error",
        "today":   {
            "date": "", "value": None, "unit": "USD/kg",
            "grade": "", "change_val": None, "change_pct": None
        },
        "history": [],
    }

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\n✅ data/prices.json 저장 완료!")
