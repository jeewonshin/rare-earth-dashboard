import requests
import json
import os
from datetime import datetime

print("📡 KOMIS 희토류 가격 수집 중...")

URL = "https://www.komis.or.kr/Komis/RsrcPrice/ajax/getChartData"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

# ── 수집할 광종 목록 ───────────────────────────────────────
METALS = [
    {
        "name":   "네오디뮴 (Nd)",
        "grade":  "99.5%min FOB China",
        "code":   "MNRL1001",
        "crtr":   "757",
        "spcfct": "99.5",
    },
    {
        "name":   "세륨 (Ce)",
        "grade":  "99%min FOB China",
        "code":   "MNRL1002",
        "crtr":   "802",
        "spcfct": "99",
    },
    {
        "name":   "망간 (Mn)",
        "grade":  "75%min FOB China",
        "code":   "MNRL0004",
        "crtr":   "815",
        "spcfct": "75",
        "unit":   "USD/mt",          # ← Mn도 mt 단위
    },
    {
        "name":   "창연 (Bi)",
        "grade":  "99.99%min FOB China",
        "code":   "MNRL0020",
        "crtr":   "789",
        "spcfct": "99.99",
        "unit":   "USD/mt",          # ← Bi는 mt 단위
    },
]

def fetch_metal(metal):
    """KOMIS에서 특정 광종의 차트 데이터를 가져옵니다."""
    unit = metal.get("unit", "USD/kg")   # ← 광종별 단위 (기본 USD/kg)

    params = {
        "mnrkndUnqRadioCd":       metal["code"],
        "srchMnrkndUnqCd":        metal["code"],
        "srchPrcCrtr":            metal["crtr"],
        "spcfct":                 metal["spcfct"],
        "srchAvgOpt":             "DAY",
        "srchField":              "year",
        "srchStartDate":          "2024",
        "srchEndDate":            str(datetime.now().year),
        "srchCompareMnrkndUnqCd": "",
        "srchComparePrcCrtr":     "",
        "lmeInvt":                "Y",
        "HP000":                  "HP002",
    }

    res = requests.post(URL, data=params, headers=HEADERS, timeout=20)
    res.raise_for_status()
    raw = res.json()

    # xaxis / series[0].data 파싱
    xaxis  = raw["data"]["xaxis"]
    yaxis  = raw["data"]["series"][0]["data"]

    history = []
    for d, v in zip(xaxis, yaxis):
        try:
            if v is not None and v != "" and v != "-":
                history.append({"date": str(d).strip(), "value": float(v)})
        except:
            pass

    # 오늘 가격 / 등락
    today_price = today_date = change_val = change_pct = None
    if history:
        today_price = history[-1]["value"]
        today_date  = history[-1]["date"]
        if len(history) >= 2:
            prev       = history[-2]["value"]
            change_val = round(today_price - prev, 4)
            change_pct = round((change_val / prev) * 100, 2) if prev else 0

    return {
        "name":       metal["name"],
        "grade":      metal["grade"],
        "today": {
            "date":       today_date or "",
            "value":      today_price,
            "unit":       unit,          # ← 광종별 단위 적용
            "change_val": change_val,
            "change_pct": change_pct,
        },
        "history": history,
    }


# ── 메인 실행 ──────────────────────────────────────────────
results = []

for metal in METALS:
    print(f"\n  수집 중: {metal['name']}")
    try:
        data = fetch_metal(metal)
        results.append(data)
        print(f"  ✅ {data['today']['value']} {data['today']['unit']} ({len(data['history'])}건)")
    except Exception as e:
        print(f"  ❌ 실패: {e}")
        results.append({
            "name":    metal["name"],
            "grade":   metal["grade"],
            "today":   {"date": "", "value": None,
                        "unit": metal.get("unit", "USD/kg"),
                        "change_val": None, "change_pct": None},
            "history": [],
        })

os.makedirs("data", exist_ok=True)

output = {
    "updated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    "source":     "KOMIS (한국자원정보서비스)",
    "source_url": "https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals",
    "metals":     results,
}

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ 저장 완료! ({len(results)}종)")
