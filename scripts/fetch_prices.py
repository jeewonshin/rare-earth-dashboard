import json
from datetime import datetime

# 초기에는 수동 업데이트 or 뉴스 기반 참고값으로 시작
# 추후 Metals-API 등으로 자동화 가능
prices = {
    "updated": datetime.now().strftime("%Y-%m-%d"),
    "items": [
        {"name": "Neodymium (Nd)", "value": "~82", "unit": "USD/kg"},
        {"name": "Praseodymium (Pr)", "value": "~84", "unit": "USD/kg"},
        {"name": "Dysprosium (Dy)", "value": "~290", "unit": "USD/kg"},
        {"name": "Cerium (Ce)", "value": "~2.5", "unit": "USD/kg"},
        {"name": "Terbium (Tb)", "value": "~1,050", "unit": "USD/kg"}
    ]
}

with open("data/prices.json", "w", encoding="utf-8") as f:
    json.dump(prices, f, ensure_ascii=False, indent=2)
print("✅ 가격 데이터 저장")
