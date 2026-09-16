import csv
import os
from datetime import date
from decimal import Decimal
from pathlib import Path

import psycopg
from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[2]
# 실행기가 전달한 날짜의 CSV를 적재합니다.
TRADE_DATE = os.getenv("KRX_TRADE_DATE", "20260904")
INPUT_PATH = PROJECT_ROOT / "data" / "processed" / f"kospi_{TRADE_DATE}.csv"

# 날짜와 종목코드를 복합 기본키로 묶어 하루에 종목당 한 행만 저장합니다.
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS kospi_daily_prices (
    trade_date DATE NOT NULL,
    ticker TEXT NOT NULL,
    stock_name TEXT,
    market TEXT,
    section_type TEXT,
    close_price BIGINT,
    change_price BIGINT,
    change_rate NUMERIC,
    open_price BIGINT,
    high_price BIGINT,
    low_price BIGINT,
    volume BIGINT,
    trading_value BIGINT,
    market_cap BIGINT,
    listed_shares BIGINT,
    PRIMARY KEY (trade_date, ticker)
)
"""

# 같은 기본키가 있으면 기존 값을 갱신합니다. 재실행해도 행이 중복되지 않습니다.
# 값은 SQL 문자열에 붙이지 않고 psycopg의 매개변수로 전달합니다.
UPSERT_SQL = """
INSERT INTO kospi_daily_prices (
    trade_date, ticker, stock_name, market, section_type,
    close_price, change_price, change_rate, open_price, high_price,
    low_price, volume, trading_value, market_cap, listed_shares
) VALUES (
    %(trade_date)s, %(ticker)s, %(stock_name)s, %(market)s, %(section_type)s,
    %(close_price)s, %(change_price)s, %(change_rate)s, %(open_price)s,
    %(high_price)s, %(low_price)s, %(volume)s, %(trading_value)s,
    %(market_cap)s, %(listed_shares)s
)
ON CONFLICT (trade_date, ticker) DO UPDATE SET
    stock_name = EXCLUDED.stock_name,
    market = EXCLUDED.market,
    section_type = EXCLUDED.section_type,
    close_price = EXCLUDED.close_price,
    change_price = EXCLUDED.change_price,
    change_rate = EXCLUDED.change_rate,
    open_price = EXCLUDED.open_price,
    high_price = EXCLUDED.high_price,
    low_price = EXCLUDED.low_price,
    volume = EXCLUDED.volume,
    trading_value = EXCLUDED.trading_value,
    market_cap = EXCLUDED.market_cap,
    listed_shares = EXCLUDED.listed_shares
"""


def main():
    # DB 접속 정보는 .env에서 읽고 화면에 출력하지 않습니다.
    load_dotenv(PROJECT_ROOT / ".env")
    db_config = {
        "host": os.environ["PGHOST"],
        "port": os.environ["PGPORT"],
        "dbname": os.environ["PGDATABASE"],
        "user": os.environ["PGUSER"],
        "password": os.environ["PGPASSWORD"],
        "connect_timeout": 10,
    }

    integer_columns = [
        "close_price", "change_price", "open_price", "high_price",
        "low_price", "volume", "trading_value", "market_cap", "listed_shares",
    ]

    # CSV를 문자열로 읽어 종목코드 앞자리 0을 유지합니다.
    with INPUT_PATH.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))

    # 빈 값은 SQL NULL로, 날짜와 숫자는 DB에 맞는 타입으로 변환합니다.
    for row in rows:

        for column, value in row.items():
            row[column] = None if value == "" else value
        row["trade_date"] = date.fromisoformat(row["trade_date"])
        for column in integer_columns:
            if row[column] is not None:
                row[column] = int(row[column])
        if row["change_rate"] is not None:
            row["change_rate"] = Decimal(row["change_rate"])


    # 파일 전체를 한 트랜잭션으로 처리합니다.
    # with를 정상 종료하면 커밋하고, 예외가 나면 전체 롤백한 뒤 오류를 전달합니다.
    with psycopg.connect(**db_config) as conn:
        with conn.cursor() as cur:
            cur.execute(CREATE_TABLE_SQL)
            cur.executemany(UPSERT_SQL, rows)

    print("loaded rows:", len(rows))
    print("table: kospi_daily_prices")


if __name__ == "__main__":
    main()
