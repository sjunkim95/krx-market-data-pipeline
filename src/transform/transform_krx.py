import os
import json
from pathlib import Path

import pandas as pd



PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 실행기가 전달한 날짜의 원본과 정제 파일을 사용합니다.
TRADE_DATE = os.getenv("KRX_TRADE_DATE", "20260904")


input_path = PROJECT_ROOT / "data" / "raw" / f"kospi_{TRADE_DATE}.json"
output_dir = PROJECT_ROOT / "data" / "processed"
output_dir.mkdir(parents=True, exist_ok=True)

output_path = output_dir / f"kospi_{TRADE_DATE}.csv"



# 원본 JSON에서 종목 목록을 꺼내 표 형태로 변환합니다.
with open(input_path, "r", encoding="utf-8") as f:
    data = json.load(f)



rows = data.get("OutBlock_1", [])

print("raw rows:", len(rows))



df = pd.DataFrame(rows)



# 적재에 필요한 컬럼을 선택하고 DB에서 사용할 이름으로 통일합니다.
column_map = {
    "BAS_DD": "trade_date",
    "ISU_CD": "ticker",
    "ISU_NM": "stock_name",
    "MKT_NM": "market",
    "SECT_TP_NM": "section_type",
    "TDD_CLSPRC": "close_price",
    "CMPPREVDD_PRC": "change_price",
    "FLUC_RT": "change_rate",
    "TDD_OPNPRC": "open_price",
    "TDD_HGPRC": "high_price",
    "TDD_LWPRC": "low_price",
    "ACC_TRDVOL": "volume",
    "ACC_TRDVAL": "trading_value",
    "MKTCAP": "market_cap",
    "LIST_SHRS": "listed_shares",
}

df = df[list(column_map.keys())].rename(columns=column_map)



# 날짜를 날짜 타입으로 바꿔 CSV에 일관된 형식으로 저장합니다.
df["trade_date"] = pd.to_datetime(
    df["trade_date"],
    format="%Y%m%d"
)



# 숫자 문자열을 변환합니다. 변환할 수 없는 값은 결측값이 됩니다.
integer_columns = [
    "close_price",
    "change_price",
    "open_price",
    "high_price",
    "low_price",
    "volume",
    "trading_value",
    "market_cap",
    "listed_shares",
]

for col in integer_columns:
    df[col] = pd.to_numeric(df[col], errors="coerce")


df["change_rate"] = pd.to_numeric(
    df["change_rate"],
    errors="coerce"
)



# 정제 결과의 일부와 타입, 행 수를 실행 화면에서 확인합니다.
print(df.head())
print()
print(df.dtypes)
print()
print("processed rows:", len(df))



# 엑셀에서도 한글을 읽을 수 있도록 UTF-8 BOM을 포함해 저장합니다.
df.to_csv(
    output_path,
    index=False,
    encoding="utf-8-sig"
)

print("saved:", output_path)
