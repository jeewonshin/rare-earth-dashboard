import requests
import json
import os
from datetime import datetime

print("📡 KOMIS 네오디뮴 가격 수집 중...")

URL = "https://www.komis.or.kr/Komis/RsrcPrice/ajax/getMnrlPriceCrtr"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0.0.0 Safari/537.36",
    "Referer": "https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals",
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8",
    "X-Requested-With": "XMLHttpRequest",
}

PARAMS = {
    "HP000": "",
    "HP002": "",
    "mnrkndUnqCd": "MNRL1001",   # 네오디뮴 고유 코드
}

try:
    res = requests.post(URL, data=PARAMS, headers=HEADERS, timeout=15)
    res.raise_for_status()
    raw = res.json()
    print("응답 원본:", json.dumps(raw, ensure_ascii=False, indent=2)[:300])

    # data 배열에서 첫 번째 항목 추출
    data_list = raw.get("data", [])
    
    # "Neodymium Oxide" 항목 찾기
    nd_item = next(
        (d for d in data_list if "Neodymium" in d.get("cdVal", "")),
        data_list[0] if data_list else None
    )

    if nd_item:
        price_value = nd_item.get("spcfct", "N/A")
        grade       = nd_item.get("cdVal", "Neodymium Oxide")
        print(f"✅ 네오디뮴 가격: {price_value} | 등급: {grade}")
    else:
        price_value = "N/A"
        grade = "Neodymium Oxide"
        print("⚠️ 데이터 없음")

    items = [{
        "name":  "네오디뮴 (Nd)",
        "grade": grade,
        "value": price_value,
        "unit":  "USD/kg",
        "date":  datetime.now().strftime("%Y-%m-%d"),
    }]
    status = "success"

except Exception as e:
    print(f"❌ 오류: {e}")
    items = [{
        "name":  "네오디뮴 (Nd)",
        "grade": "Neodymium Oxide",
        "value": "N/A",
        "unit":  "USD/kg",
        "date":  datetime.now().strftime("%Y-%m-%d"),
    }]
    status = "error"

os.makedirs("data", exist_ok=True)

output = {
    "updated":    datetime.now().strftime("%Y-%m-%d %H:%M"),
    "source":     "KOMIS (한국자원정보서비스)",
    "source_url": "https://www.komis.or.kr/Komis/RsrcPrice/MinorMetals",
    "status":     status,
    "items":      items,
}

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(output, f, ensure_ascii=False, indent=2)

print(f"✅ 저장 완료!")
