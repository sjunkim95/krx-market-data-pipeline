import os
import json
from pathlib import Path

import requests
from dotenv import load_dotenv



# 실행 위치와 관계없이 프로젝트 폴더를 찾습니다.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 실행기가 전달한 날짜를 사용합니다. 단독 실행의 기본값은 기존 기준일입니다.
TRADE_DATE = os.getenv("KRX_TRADE_DATE", "20260904")


# 인증키는 코드에 넣지 않고 .env에서 읽어 요청 헤더로 전달합니다.
load_dotenv(PROJECT_ROOT / ".env")

API_KEY = os.getenv("KRX_API_KEY")

URL = "https://data-dbg.krx.co.kr/svc/apis/sto/stk_bydd_trd"

headers = {
    "AUTH_KEY": API_KEY
}

params = {
    "basDd": TRADE_DATE
}

# 응답을 최대 30초 기다리며, HTTP 오류는 다음 단계로 넘기지 않습니다.
response = requests.get(
    URL,
    headers=headers,
    params=params,
    timeout=30
)

response.raise_for_status()

data = response.json()


# 응답 형식 오류와 데이터 없는 날을 구분합니다.
if not isinstance(data, dict) or not isinstance(data.get("OutBlock_1"), list):
    raise ValueError("Invalid KRX response: OutBlock_1 must be a list")
rows = data["OutBlock_1"]
# 비거래일 등 정상 응답이 빈 목록이면 코드 10으로 SKIP을 알립니다.
if not rows:
    print(f"SKIP date={TRADE_DATE} rows=0")
    raise SystemExit(10)

print("rows:", len(rows))



# 원본 응답을 날짜별로 보관해 정제 과정에서 다시 읽습니다.
output_dir = PROJECT_ROOT / "data" / "raw"
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / f"kospi_{TRADE_DATE}.json"

with open(output_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

print("saved:", output_path)
