import requests
import json
import os
import time
from datetime import datetime

# ── Cloudflare Worker 프록시를 통해 KOMIS 데이터 수집 ─────────────────────────
# Worker URL: https://komis-proxy.jeewon00-shin.workers.dev
# Cloudflare 서울 엣지 서버 경유 → KOMIS IP 차단 우회

print("📡 KOMIS 희토류 가격 수집 중...")

# ✅ Cloudflare Worker URL (KOMIS 직접 접속 대신 Worker 경유)
URL = "https://komis-proxy.jeewon00-shin.workers.dev"

HEADERS = {
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
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
        "unit":   "USD/mt",
    },
    {
        "name":   "창연 (Bi)",
        "grade":  "99.99%min FOB China",
        "code":   "MNRL0020",
        "crtr":   "789",
        "spcfct": "99.99",
        "unit":   "USD/mt",
    },
]


def fetch_metal(metal):
    """Cloudflare Worker를 통해 KOMIS 가격 데이터를 가져옵니다. (최대 3회 재시도)"""
    unit = metal.get("unit", "USD/kg")

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

    last_error = None
    for attempt in range(3):
        try:
            print(f"  시도 {attempt + 1}/3...")
            # ✅ Worker가 KOMIS 헤더/쿠키를 대신 처리
            res = requests.post(URL, data=params, headers=HEADERS, timeout=40)
            res.raise_for_status()
            raw = res.json()

            xaxis = raw["data"]["xaxis"]
            yaxis = raw["data"]["series"][0]["data"]

            history = []
            for d, v in zip(xaxis, yaxis):
                try:
                    if v is not None and v != "" and v != "-":
                        history.append({"date": str(d).strip(), "value": float(v)})
                except:
                    pass

            today_price = today_date = change_val = change_pct = None
            if history:
                today_price = history[-1]["value"]
                today_date  = history[-1]["date"]
                if len(history) >= 2:
                    prev       = history[-2]["value"]
                    change_val = round(today_price - prev, 4)
                    change_pct = round((change_val / prev) * 100, 2) if prev else 0

            return {
                "name":  metal["name"],
                "grade": metal["grade"],
                "today": {
                    "date":       today_date or "",
                    "value":      today_price,
                    "unit":       unit,
                    "change_val": change_val,
                    "change_pct": change_pct,
                },
                "history": history,
            }

        except requests.exceptions.Timeout:
            last_error = f"타임아웃 (시도 {attempt + 1}/3)"
            print(f"  ⏱ {last_error}")
            if attempt < 2:
                wait = 3 * (attempt + 1)
                print(f"  ⏳ {wait}초 후 재시도...")
                time.sleep(wait)

        except Exception as e:
            last_error = str(e)
            print(f"  ⚠ 오류: {e}")
            if attempt < 2:
                print(f"  ⏳ 3초 후 재시도...")
                time.sleep(3)

    raise Exception(f"3회 모두 실패: {last_error}")


# ── 기존 데이터 로드 (fallback용) ───────────────────────────
existing_data = {}
try:
    with open("data/prices.json", "r", encoding="utf-8") as f:
        old = json.load(f)
    for m in old.get("metals", []):
        existing_data[m["name"]] = m
    print(f"📂 기존 데이터 로드 완료 ({len(existing_data)}종)")
except:
    print("📂 기존 데이터 없음 (첫 실행)")

# ── 메인 수집 루프 ───────────────────────────────────────────
results = []

for metal in METALS:
    print(f"\n  수집 중: {metal['name']} (최대 3회 시도)")
    try:
        data = fetch_metal(metal)
        results.append(data)
        print(f"  ✅ {data['today']['value']} {data['today']['unit']} ({len(data['history'])}건)")

    except Exception as e:
        print(f"  ❌ 실패: {e}")

        # ── fallback: 기존 데이터 유지 ──
        if metal["name"] in existing_data:
            old_metal = existing_data[metal["name"]]
            results.append(old_metal)
            print(f"  🔄 기존 데이터 유지: {metal['name']} "
                  f"({old_metal['today'].get('date', '날짜 미상')})")
        else:
            results.append({
                "name":    metal["name"],
                "grade":   metal["grade"],
                "today":   {
                    "date": "", "value": None,
                    "unit": metal.get("unit", "USD/kg"),
                    "change_val": None, "change_pct": None
                },
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
