import argparse
import logging
import subprocess
import sys
from datetime import timedelta
from pathlib import Path

# 단일 날짜 실행기와 같은 날짜 검증 함수를 사용합니다.
from run_pipeline import parse_date


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def main():
    # 시작일과 종료일을 받아 잘못된 날짜나 뒤집힌 범위를 실행 전에 막습니다.
    parser = argparse.ArgumentParser()
    parser.add_argument("start_date", type=parse_date)
    parser.add_argument("end_date", type=parse_date)
    try:
        args = parser.parse_args()
        if args.start_date > args.end_date:
            parser.error("start_date must be on or before end_date")
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1

    # 날짜별 요약은 backfill 로그에, 단계별 내용은 pipeline 로그에 남깁니다.
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        filename=log_dir / "run_backfill.log",
        encoding="utf-8",
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    logging.info("BACKFILL START start=%s end=%s", args.start_date, args.end_date)
    success = 0
    skipped = 0
    current = args.start_date
    # 시작일과 종료일을 포함해 하루씩 처리합니다. 주말도 API 응답으로 판단합니다.
    while current <= args.end_date:
        trade_date = current.strftime("%Y%m%d")
        logging.info("START date=%s", trade_date)
        try:

            # 현재 가상환경에서 기존 실행기를 호출해 단계 로직을 재사용합니다.
            # SKIP 코드 10도 받아야 하므로 check=False로 종료 코드를 직접 확인합니다.
            result = subprocess.run(
                [sys.executable, "-X", "utf8",
                 str(PROJECT_ROOT / "src" / "run_pipeline.py"), trade_date],
                cwd=PROJECT_ROOT,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=False,
            )
            # 성공 0과 데이터 없음 10만 계속 진행하고, 실제 오류는 즉시 중단합니다.
            if result.returncode not in (0, 10):
                raise RuntimeError((result.stderr or result.stdout).strip())
        except (OSError, RuntimeError) as exc:
            logging.error("BACKFILL FAILED date=%s error=%s", trade_date, exc)
            print(f"BACKFILL FAILED date={trade_date}: {exc}", file=sys.stderr)
            return 1


        # 데이터 없는 날은 실패가 아닌 SKIP으로 집계합니다.
        status = "SUCCESS" if result.returncode == 0 else "SKIP"
        success += result.returncode == 0
        skipped += result.returncode == 10
        logging.info("%s date=%s", status, trade_date)
        print(f"{status} date={trade_date}", flush=True)
        if current == args.end_date:
            break
        # 다음 날짜로 넘어갑니다. 종료일을 처리한 뒤에는 반복을 끝냅니다.
        current += timedelta(days=1)

    logging.info("BACKFILL SUCCESS success=%s skip=%s", success, skipped)
    print(f"BACKFILL SUCCESS success={success} skip={skipped}")
    return 0


# 전체 범위를 마치면 0, 도중 오류로 중단하면 1을 반환합니다.
if __name__ == "__main__":
    sys.exit(main())
