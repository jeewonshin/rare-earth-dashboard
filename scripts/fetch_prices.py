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

    print("응답 원본 (앞 500자):")
    print(json.dumps(raw, ensure_ascii=False, indent=2)[:500])

    # ── 차트 히스토리 데이터 키 탐색 ──────────────────────
    chart_list = []
    for key in ["chartData", "data", "priceList", "list", "result"]:
        if key in raw and isinstance(raw[key], list):
            chart_list = raw[key]
            print(f"차트 데이터 키: '{key}', 건수: {len(chart_list)}")
            break
    if not chart_list and isinstance(raw, list):
        chart_list = raw
        print(f"raw 자체가 리스트, 건수: {len(chart_list)}")

    # ── 날짜/가격 필드명 자동 탐색 ────────────────────────
    history = []
    if chart_list:
        sample = chart_list[0]
        print("첫 번째 항목 키:", list(sample.keys()))

        date_key  = next((k for k in sample if any(x in k.lower() for x in ["date","dt","ymd","기준"])), None)
        price_key = next((k for k in sample if any(x in k.lower() for x in ["price","prc","val","가격"])), None)
        print(f"날짜 필드: {date_key}, 가격 필드: {price_key}")

        for item in chart_list:
            d = str(item.get(date_key, "")).strip()
            p = item.get(price_key, None)
            if d and p is not None:
                try:
                    history.append({"date": d, "value": float(p)})
                except:
                    pass

    print(f"히스토리 파싱 건수: {len(history)}")

    # ── 오늘 가격 / 등락 계산 ─────────────────────────────
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
        "today":   {"date": "", "value": None, "unit": "USD/kg",
                    "grade": "", "change_val": None, "change_pct": None},
        "history": [],
    }

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print("\n✅ data/prices.json 저장 완료!")
