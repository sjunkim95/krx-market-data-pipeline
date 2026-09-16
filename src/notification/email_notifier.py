import logging
import os
import smtplib
import ssl
from datetime import datetime
from email.message import EmailMessage


def send_notification(status, processing_date, rows_processed=None,
                      last_date=None, stage=None, error=None):
    # SKIP은 알리지 않고, 설정이 비어 있으면 메일 기능만 건너뜁니다.
    if status == "SKIP":
        return False
    try:
        sender = os.getenv("EMAIL_FROM", "").strip()
        recipient = os.getenv("EMAIL_TO", "").strip()
        password = os.getenv("EMAIL_APP_PASSWORD", "").replace(" ", "")
        if not all((sender, recipient, password)):
            logging.info("EMAIL NOT_CONFIGURED")
            return False

        completed = datetime.now().astimezone().isoformat(timespec="seconds")
        body = f"처리 날짜: {processing_date}\npipeline 상태: {status}\n"
        if status == "SUCCESS":
            body += f"처리된 행 수: {rows_processed}\nDB 마지막 적재 날짜: {last_date}\n"
        else:
            body += f"실패 단계: {stage}\n오류 메시지: {error}\n"
        body += f"실행 완료 시간: {completed}"
        # 오류 내용에 환경변수의 인증정보가 섞여 있어도 메일 본문에서 가립니다.
        for key in ("KRX_API_KEY", "PGPASSWORD", "PGUSER", "EMAIL_FROM",
                    "EMAIL_TO", "EMAIL_APP_PASSWORD"):
            value = os.getenv(key)
            if value:
                body = body.replace(value, "[REDACTED]")
        body = body.replace(password, "[REDACTED]")
        message = EmailMessage()
        message["Subject"] = f"KRX Pipeline {status} - {datetime.now():%Y-%m-%d}"
        message["From"] = sender
        message["To"] = recipient
        message.set_content(body)

        # SMTP는 메일 전송 연결입니다. TLS로 암호화한 뒤 Gmail 앱 비밀번호로 로그인합니다.
        with smtplib.SMTP(os.getenv("SMTP_HOST") or "smtp.gmail.com",
                          int(os.getenv("SMTP_PORT") or "587"), timeout=30) as smtp:
            smtp.ehlo()
            smtp.starttls(context=ssl.create_default_context())
            smtp.ehlo()
            smtp.login(sender, password)
            smtp.send_message(message)
        logging.info("EMAIL SENT status=%s", status)
        return True
    except Exception as exc:
        # 메일 장애로 이미 끝난 적재를 실패 처리하지 않습니다. 계정 정보도 기록하지 않습니다.
        logging.warning("EMAIL FAILED error_type=%s", type(exc).__name__)
        return False
