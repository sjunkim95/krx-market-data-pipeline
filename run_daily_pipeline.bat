@echo off
setlocal
REM 배치 파일이 있는 프로젝트 루트로 이동합니다.
cd /d "%~dp0"
if errorlevel 1 exit /b 1
REM 프로젝트 가상환경의 Python으로 누락 날짜 복구 실행기을 실행합니다.
".venv\Scripts\python.exe" -X utf8 "src\run_daily_pipeline.py"
REM Python의 종료 코드를 저장합니다. 성공은 0, 실제 오류는 1입니다.
set "PIPELINE_EXIT=%ERRORLEVEL%"
REM 데이터 없음은 정상 상황이므로 SKIP 10을 Windows에는 성공 0으로 전달합니다.
if "%PIPELINE_EXIT%"=="10" exit /b 0
exit /b %PIPELINE_EXIT%
