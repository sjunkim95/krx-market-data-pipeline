import os
from pathlib import Path
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 실행기가 전달한 날짜의 정제 CSV를 검사합니다.
TRADE_DATE = os.getenv("KRX_TRADE_DATE", "20260904")


input_path = PROJECT_ROOT / "data" / "processed" / f"kospi_{TRADE_DATE}.csv"



# 종목코드 앞자리 0을 유지하도록 문자열로 읽습니다.
df = pd.read_csv(
    input_path,
    dtype={"ticker": str}
)



# DB 기본키에 사용할 날짜와 종목코드의 누락·중복을 확인합니다.
missing_trade_date = df["trade_date"].isna().sum()
missing_ticker = df["ticker"].isna().sum()



duplicate_count = df.duplicated(
    subset=["trade_date", "ticker"]
).sum()



# 거래량과 시가총액의 음수는 오류로 취급합니다.
negative_volume = (df["volume"] < 0).sum()
negative_market_cap = (df["market_cap"] < 0).sum()


# 거래량 0은 참고용으로 출력하고 실패 조건에는 넣지 않습니다.
zero_volume_count = (df["volume"] == 0).sum()



# 실제 거래가 있는 행만 고가·저가와 시가·종가의 범위를 검사합니다.
traded = df["volume"] > 0


invalid_high_low = (
    traded & (df["high_price"] < df["low_price"])
).sum()


invalid_open = (
    traded & (
        (df["open_price"] > df["high_price"]) |
        (df["open_price"] < df["low_price"])
    )
).sum()


invalid_close = (
    traded & (
        (df["close_price"] > df["high_price"]) |
        (df["close_price"] < df["low_price"])
    )
).sum()



# 항목별 오류 건수를 출력해 실패 원인을 확인할 수 있게 합니다.
print("=== Data Quality Check ===")
print("rows:", len(df))
print("missing trade_date:", missing_trade_date)
print("missing ticker:", missing_ticker)
print("duplicates:", duplicate_count)
print("negative volume:", negative_volume)
print("zero volume:", zero_volume_count)
print("negative market_cap:", negative_market_cap)
print("high < low:", invalid_high_low)
print("invalid open:", invalid_open)
print("invalid close:", invalid_close)


# 오류가 있으면 실패 종료합니다. 실행기는 여기서 멈추고 load를 실행하지 않습니다.
errors = {
    "missing trade_date": missing_trade_date,
    "missing ticker": missing_ticker,
    "duplicates": duplicate_count,
    "negative volume": negative_volume,
    "negative market_cap": negative_market_cap,
    "high < low": invalid_high_low,
    "invalid open": invalid_open,
    "invalid close": invalid_close,
}
failed_checks = [f"{name}={count}" for name, count in errors.items() if count > 0]
if failed_checks:
    raise SystemExit("Validation failed: " + ", ".join(failed_checks))
