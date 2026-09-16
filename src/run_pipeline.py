import argparse
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path



# 다른 폴더에서 실행해도 파일과 로그 경로는 프로젝트 루트를 기준으로 잡습니다.
PROJECT_ROOT = Path(__file__).resolve().parents[1]

# 앞 단계가 성공해야 다음 단계로 넘어갑니다.
STEPS = [
    ("extract", "src/extract/extract_krx.py"),
    ("transform", "src/transform/transform_krx.py"),
    ("validation", "src/validation/validate_krx.py"),
    ("load", "src/load/load_krx.py"),
]



# YYYYMMDD 형식과 실제 달력에 존재하는 날짜인지 함께 검사합니다.
def parse_date(value):

    if len(value) != 8 or not value.isascii() or not value.isdigit():
        raise argparse.ArgumentTypeError("Date must be YYYYMMDD")
    try:

        return datetime.strptime(value, "%Y%m%d").date()
    except ValueError as exc:

        raise argparse.ArgumentTypeError("Invalid calendar date") from exc


def main():

    # argparse로 실행할 날짜를 받습니다. 생략하면 PC의 오늘 날짜를 사용합니다.
    parser = argparse.ArgumentParser()

    parser.add_argument("date", nargs="?", default=datetime.now().strftime("%Y%m%d"), type=parse_date)

    # 입력 오류도 실제 실패 코드 1로 통일합니다. --help는 정상 종료합니다.
    try:
        trade_date = parser.parse_args().date.strftime("%Y%m%d")
    except SystemExit as exc:
        return 0 if exc.code == 0 else 1



    # 각 단계가 같은 날짜를 처리하도록 환경변수로 전달합니다.
    env = os.environ.copy()
    env["KRX_TRADE_DATE"] = trade_date


    # 실행 시각, 조회 날짜, 단계별 결과를 기존 로그에 이어서 기록합니다.
    log_dir = PROJECT_ROOT / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)

    logging.basicConfig(
        filename=log_dir / "run_pipeline.log",
        encoding="utf-8",
        level=logging.INFO,
        format=f"%(asctime)s %(levelname)s date={trade_date} %(message)s",
    )
    logging.info("PIPELINE START")


    for name, script in STEPS:
        logging.info("%s START", name)
        try:



            # subprocess는 각 파일이 끝날 때까지 기다립니다.
            # sys.executable로 현재 가상환경의 Python을 그대로 사용합니다.
            # check=True는 0이 아닌 종료 코드를 CalledProcessError로 바꿉니다.
            result = subprocess.run(
                [sys.executable, "-X", "utf8", str(PROJECT_ROOT / script)],
                cwd=PROJECT_ROOT,
                env=env,
                capture_output=True,
                text=True,
                encoding="utf-8",
                check=True,
            )


        # 단계 실패 또는 실행 자체의 오류를 처리합니다.
        except (subprocess.CalledProcessError, OSError) as exc:

            # extract의 코드 10은 데이터 없음입니다. 이후 단계 없이 SKIP으로 끝냅니다.
            if name == "extract" and isinstance(exc, subprocess.CalledProcessError) and exc.returncode == 10:
                logging.info("PIPELINE SKIP rows=0")
                print(f"PIPELINE SKIP date={trade_date}")

                return 10

            # 오류 출력을 우선 기록하고, 없으면 일반 출력이나 예외 내용을 사용합니다.
            if isinstance(exc, subprocess.CalledProcessError):
                message = (exc.stderr or exc.stdout or str(exc)).strip()
            else:
                message = str(exc)
            logging.error("%s FAILED error=%s", name, message)
            logging.error("PIPELINE FAILED step=%s", name)
            print(f"{name} FAILED: {message}", file=sys.stderr)

            # 검증 실패를 포함해 실제 오류가 나면 load 등 남은 단계를 실행하지 않습니다.
            return 1


        # 단계의 일반 출력은 화면에 보여주고 성공 여부는 로그에 남깁니다.
        if result.stdout:
            print(result.stdout, end="")
        logging.info("%s SUCCESS", name)


    # 모든 단계가 통과한 경우에만 전체 성공으로 종료합니다.
    logging.info("PIPELINE SUCCESS")
    print("PIPELINE SUCCESS")
    return 0




# 직접 실행할 때만 시작합니다. import할 때는 실행하지 않습니다.
# 종료 코드: 0 성공, 1 실패(입력 오류 포함), 10 SKIP.
if __name__ == "__main__":
    sys.exit(main())
