# KRX KOSPI 일별 데이터 파이프라인

KRX API에서 KOSPI 종목별 일별 시장 데이터를 수집하고, 정제·검증한 뒤 PostgreSQL에 저장하는 Python 프로젝트입니다. 날짜별 재실행, 과거 데이터 수집, 일일 예약 실행을 직접 구현하며 데이터 적재 과정을 학습했습니다.

## 처리 흐름

```text
KRX API → Raw JSON → pandas 정제 → CSV → 데이터 검증 → PostgreSQL
```

- **Extract:** 조회 날짜의 API 응답을 JSON으로 보관합니다. HTTP 오류나 응답 형식 오류는 실패로 처리합니다.
- **Transform:** 필요한 15개 컬럼을 선택하고 날짜·숫자 타입을 변환합니다.
- **Validation:** 날짜·종목코드 결측, 중복, 거래량·시가총액 음수, OHLC 범위를 검사합니다. OHLC 검사는 거래량이 양수인 행에만 적용하며, 거래량 0은 참고 항목입니다.
- **Load:** `psycopg`와 SQL로 적재합니다. 종목코드는 문자열로 유지합니다.

검증에 실패하면 적재하지 않습니다. `kospi_daily_prices`의 복합 Primary Key는 `(trade_date, ticker)`입니다. `ON CONFLICT ... DO UPDATE`로 기존 행을 갱신하므로 같은 날짜를 다시 실행해도 중복 행이 생기지 않습니다. 한 CSV의 적재는 하나의 transaction이며, 성공 시 commit하고 오류 시 전체 rollback합니다.

## 실행 제어

- `run_pipeline.py`: 한 날짜의 네 단계를 순서대로 실행합니다. 날짜를 생략하면 PC의 오늘 날짜를 사용합니다.
- `run_backfill.py`: 시작일부터 종료일까지 하루씩 기존 pipeline을 호출합니다. 실제 오류가 발생하면 해당 날짜에서 중단합니다.
- KRX가 정상 응답으로 빈 목록을 반환하면 비거래일 또는 데이터 미제공으로 보고 **SKIP**합니다. 종료 코드는 성공 `0`, 실패 `1`, 정상 SKIP `10`입니다. Backfill은 SKIP을 포함한 범위를 정상 완료하면 `0`을 반환합니다.
- `run_daily_pipeline.py`: DB 마지막 적재일 다음 날부터 오늘까지 backfill합니다. 마지막 적재일 이전의 중간 누락은 자동 탐지하지 않습니다. 빈 DB에서는 최초 backfill을 먼저 해야 합니다.
- 일일 실행에서 성공한 날짜가 있으면 처리 날짜·행 수·DB 마지막 적재일을 이메일로 요약합니다. 실패 시 단계와 오류 내용을 알리고, 전부 SKIP이면 메일을 보내지 않습니다. SMTP 장애는 적재 결과를 바꾸지 않습니다.

## 검증한 backfill 결과

2026-01-01~2026-09-15 범위의 당시 DB 조회 결과입니다.

| 항목 | 결과 |
|---|---:|
| 적재 거래일 | 173일 |
| 적재 행 수 | 163,997행 |
| 날짜+종목코드 중복 | 0건 |

DB에 없는 날짜는 기존 KRX 조회의 SKIP 기록과 대조했습니다. 별도 공식 거래일 달력과 대조한 결과는 아닙니다. 운영 데이터와 로그는 저장소에 포함하지 않습니다.

## 프로젝트 구조

```text
src/
  extract/extract_krx.py
  transform/transform_krx.py
  validation/validate_krx.py
  load/load_krx.py
  notification/email_notifier.py
  run_pipeline.py
  run_backfill.py
  run_daily_pipeline.py
run_daily_pipeline.bat
requirements.txt
.env.example
data/raw/          # 실행 시 생성, Git 제외
data/processed/    # 실행 시 생성, Git 제외
logs/             # 실행 시 생성, Git 제외
```

## 설치 및 설정

개발 환경은 Windows와 Python 3.12입니다. PostgreSQL 서버와 KRX API 인증키가 필요합니다. 아래 명령은 프로젝트 루트의 PowerShell에서 실행합니다.

```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
```

PostgreSQL 관리자 계정에서 프로젝트용 계정과 DB를 생성합니다. 다음 비밀번호는 예시이므로 실제 사용할 값으로 변경합니다.

```sql
CREATE USER krx_user WITH PASSWORD 'REPLACE_WITH_YOUR_PASSWORD';
CREATE DATABASE krx_market_data OWNER krx_user;
```

`.env.example`에는 다음 항목이 있습니다. 복사한 `.env`에 실제 값을 입력하고 Git에 올리지 않습니다.

```dotenv
KRX_API_KEY=
PGHOST=localhost
PGPORT=5432
PGDATABASE=krx_market_data
PGUSER=krx_user
PGPASSWORD=
EMAIL_FROM=
EMAIL_TO=
EMAIL_APP_PASSWORD=
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
```

이메일은 선택 설정입니다. Gmail의 2단계 인증을 켜고 발급한 앱 비밀번호를 사용합니다. SMTP 연결은 STARTTLS로 암호화하며, 설정이 비어 있으면 메일 발송만 생략합니다. 조직 계정은 앱 비밀번호 사용이 제한될 수 있습니다.

## 실행

```powershell
# 최초 적재 또는 특정 날짜 재실행
.\.venv\Scripts\python.exe src\run_pipeline.py 20260904

# 과거 범위 수집: 시작일과 종료일 포함
.\.venv\Scripts\python.exe src\run_backfill.py 20260101 20260915

# 오늘 날짜만 실행
.\.venv\Scripts\python.exe src\run_pipeline.py

# DB 마지막 적재일 이후 자동 보충 및 이메일 알림
.\run_daily_pipeline.bat
```

배치 파일은 프로젝트 루트로 이동한 뒤 `.venv`의 Python으로 일일 실행기를 호출합니다. SKIP 코드 `10`은 Windows에 정상 종료 `0`으로 전달합니다. 개별 단계 파일을 직접 실행하면 환경변수가 없는 경우 기존 기준일 `20260904`를 사용하므로, 날짜 지정은 실행기를 통해 하는 것을 권장합니다.

## Windows Task Scheduler

개발 PC에는 `KRX Daily Pipeline`을 매일 한국 시간 21:00에 실행하도록 등록하고 수동 실행을 확인했습니다. 다른 PC에서는 별도 등록이 필요합니다.

| 항목 | 설정 |
|---|---|
| 프로그램 | `C:\Windows\System32\cmd.exe` |
| 인수 | `/d /c ""<프로젝트 절대 경로>\run_daily_pipeline.bat""` |
| 시작 위치 | 프로젝트 절대 경로 |
| 주기 | 매일 21:00, PC 시간대 기준 |
| 절전 | 작업 실행을 위해 절전 모드 해제 |
| 실패 재시도 | 10분 간격, 최대 3회 |
| 중복 실행 | 새 인스턴스를 시작하지 않음 |

절전 해제는 PC의 전원 설정이 지원해야 하며, 전원이 꺼진 PC를 켜는 기능은 아닙니다. 로그아웃 상태에서도 실행하려면 작업 속성에서 해당 옵션을 선택하고 Windows 계정 인증을 직접 설정해야 합니다. 네트워크 연결과 PostgreSQL 서비스도 필요합니다.

## 로그와 운영 범위

- `logs/run_pipeline.log`: 조회 날짜와 단계별 START / SUCCESS / FAILED, 데이터 없음 SKIP
- `logs/run_backfill.log`: 날짜별 요약, 일일 복구 실행 결과, 이메일 발송 결과

마지막 적재일 이후 데이터가 늦게 제공되거나 PC가 꺼져 있었다면 다음 일일 실행에서 다시 조회합니다. 더 최근 날짜가 먼저 적재되어 그 이전에 빈 날짜가 남은 경우에는 해당 구간을 수동 backfill해야 합니다. 데이터 변환 과정의 모든 결측값을 검증하는 구조는 아니며, 현재 검증은 위에 명시한 항목을 대상으로 합니다.
