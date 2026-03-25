import requests
import json
import time
from datetime import datetime

# ============================================================
# KOMIS 희소금속 가격 수집기
# 대상: 네오디뮴, 망간, 터븀, 란탄, 갈륨
# ============================================================

# KOMIS 내부 API 엔드포인트
BASE_URL = "https://www.komis.or.kr/Komis/RsrcPrice/MinorMetalsData"

# 수집할 광종 목록 (광종명: KOMIS 광종코드)
METALS = {
    "네오디뮴 (Nd)": "neodymium",
    "망간 (Mn)":     "manganese",
    "터븀 (Tb)":     "terbium",
    "란탄 (La)":     "lanthanum",
    "갈륨 (Ga)":     "gallium",
}

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Referer": "https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals",
    "Accept": "application/json, text/plain, */*",
    "X-Requested-With": "XMLHttpRequest",
}

def fetch_price(metal_code):
    """KOMIS에서 특정 광종의 최신 가격을 가져옵니다."""
    try:
        params = {
            "metalCd": metal_code,
            "avgOpt": "D",   # D=일별, M=월별
            "startDt": "",
            "endDt": "",
        }
        res = requests.get(BASE_URL, params=params, headers=HEADERS, timeout=15)
        res.raise_for_status()
        data = res.json()

        # 가장 최신 데이터 1건 추출
        if data and isinstance(data, list) and len(data) > 0:
            latest = data[-1]  # 마지막이 최신
            return {
                "date":  latest.get("priceDate", ""),
                "value": latest.get("price", "N/A"),
                "unit":  latest.get("unit", "USD/kg"),
                "change": latest.get("rateOfChange", ""),
            }
    except Exception as e:
        print(f"  ⚠️ {metal_code} 수집 실패: {e}")
    return {"date": "", "value": "N/A", "unit": "USD/kg", "change": ""}


# ── 메인 실행 ──────────────────────────────────────────────
items = []

for name, code in METALS.items():
    print(f"📡 수집 중: {name}")
    result = fetch_price(code)
    items.append({
        "name":   name,
        "value":  str(result["value"]),
        "unit":   result["unit"],
        "date":   result["date"],
        "change": str(result.get("change", "")),
    })
    time.sleep(0.5)  # 서버 부하 방지

output = {
    "updated": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "source":  "KOMIS (한국자원정보서비스)",
    "source_url": "https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals",
    "items": items
}

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"\n✅ 가격 데이터 저장 완료 ({len(items)}종)")
print(json.dumps(output, ensure_ascii=False, indent=2))
