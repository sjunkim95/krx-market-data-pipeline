import csv
import logging
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from notification.email_notifier import send_notification


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def notify_result(result, processing_date, db_config):
    # 알림용 집계가 실패해도 backfill의 종료 결과는 그대로 유지합니다.
    try:
        if result.returncode not in (0, 10):
            error = result.stderr or result.stdout or "Backfill failed"
            failed_date = re.search(r"FAILED date=(\d{8})", error)
            failed_stage = re.search(r"\b(extract|transform|validation|load) FAILED:", error)
            send_notification(
                "FAILED", failed_date[1] if failed_date else processing_date,
                stage=failed_stage[1] if failed_stage else "backfill",
                error=error,
            )
            return

        # backfill의 날짜별 SUCCESS 출력만 집계합니다. 전부 SKIP이면 메일을 보내지 않습니다.
        dates = re.findall(r"^SUCCESS date=(\d{8})$", result.stdout, re.MULTILINE)
        if not dates:
            return
        rows_processed = 0
        for day in dates:
            with (PROJECT_ROOT / "data" / "processed" / f"kospi_{day}.csv").open(
                encoding="utf-8-sig", newline=""
            ) as file:
                rows_processed += sum(1 for _ in csv.DictReader(file))
        with psycopg.connect(**db_config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(trade_date) FROM kospi_daily_prices")
                last_date = cur.fetchone()[0]
        send_notification("SUCCESS", ", ".join(dates), rows_processed, last_date)
    except Exception as exc:
        logging.warning("EMAIL SUMMARY_FAILED error_type=%s", type(exc).__name__)


def main():
    # 일일 실행의 범위 확인과 오류도 기존 backfill 로그에 기록합니다.
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "run_backfill.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("DAILY START")
    stage = "DB 날짜 확인"
    processing_date = str(date.today())
    try:
        load_dotenv(PROJECT_ROOT / ".env")
        # 날짜 확인은 읽기 전용 연결을 사용하고, 실제 적재는 기존 load에 맡깁니다.
        db_config = dict(
            host=os.environ["PGHOST"],
            port=os.environ["PGPORT"],
            dbname=os.environ["PGDATABASE"],
            user=os.environ["PGUSER"],
            password=os.environ["PGPASSWORD"],
            connect_timeout=10,
            options="-c default_transaction_read_only=on",
        )
        with psycopg.connect(**db_config) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT MAX(trade_date) FROM kospi_daily_prices")
                last_date = cur.fetchone()[0]

        # 이력이 없으면 최초 수집 범위를 임의로 정하지 않습니다.
        if last_date is None:
            logging.error("DAILY FAILED: run initial backfill first")
            send_notification("FAILED", processing_date, stage=stage,
                              error="최초 backfill 이력이 없습니다.")
            return 1

        today = date.today()
        if last_date > today:
            logging.error("DAILY FAILED: latest trade date is in the future")
            send_notification("FAILED", processing_date, stage=stage,
                              error="DB 마지막 적재 날짜가 미래입니다.")
            return 1
        if last_date == today:
            logging.info("DAILY SKIP: already up to date")
            return 10

        # 마지막 적재일 이후만 처리하므로 이미 저장된 날짜는 다시 호출하지 않습니다.
        start_date = last_date + timedelta(days=1)
        logging.info("DAILY RANGE start=%s end=%s", start_date, today)
        processing_date = f"{start_date} ~ {today}"
        stage = "backfill 실행"
        result = subprocess.run(
            [sys.executable, "-X", "utf8",
             str(PROJECT_ROOT / "src" / "run_backfill.py"),
             start_date.strftime("%Y%m%d"), today.strftime("%Y%m%d")],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )
        notify_result(result, processing_date, db_config)
        # 날짜별 SKIP은 backfill이 처리하고, 실제 실패만 일일 실행 실패로 전달합니다.
        if result.returncode not in (0, 10):
            logging.error("DAILY FAILED: backfill exit=%s", result.returncode)
            return 1
        logging.info("DAILY %s", "SUCCESS" if result.returncode == 0 else "SKIP")
        return result.returncode
    except Exception as exc:
        # 접속 정보가 예외에 섞이지 않도록 예외 종류만 남깁니다.
        logging.error("DAILY FAILED error_type=%s", type(exc).__name__)
        send_notification("FAILED", processing_date, stage=stage, error=str(exc))
        return 1


if __name__ == "__main__":
    sys.exit(main())
