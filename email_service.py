import os
import smtplib
import re
import logging
import json
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EmailService")

def validate_email_address(email):
    """
    Validates syntax of parent email addresses using standard RFC-5322 pattern.
    """
    if not email:
        return False
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, str(email).strip()))

def mask_email(email):
    """
    Masks parent email for secure display (e.g. s***a@domain.com).
    """
    if not email or '@' not in str(email):
        return "*****"
    parts = str(email).strip().split('@')
    name = parts[0]
    domain = parts[1]
    if len(name) <= 2:
        masked_name = name[0] + "*"
    else:
        masked_name = name[0] + "*" * (len(name) - 2) + name[-1]
    return f"{masked_name}@{domain}"

def mask_secret(secret):
    """
    Masks API keys or sensitive credentials for safe logging/display.
    """
    if not secret:
        return ""
    secret_str = str(secret).strip()
    if len(secret_str) <= 8:
        return "********"
    return secret_str[:3] + "********" + secret_str[-4:]

def get_email_config():
    """
    Retrieves Email settings from DB SystemSetting table or Config fallback.
    """
    try:
        from models import SystemSetting
        
        enable_set = SystemSetting.query.filter_by(key='enable_email_alerts').first()
        mode_set = SystemSetting.query.filter_by(key='email_mode').first()
        provider_set = SystemSetting.query.filter_by(key='email_provider').first()
        api_key_set = SystemSetting.query.filter_by(key='email_api_key').first()
        from_set = SystemSetting.query.filter_by(key='email_from').first()
        gmail_set = SystemSetting.query.filter_by(key='gmail_email').first()
        pass_set = SystemSetting.query.filter_by(key='gmail_app_password').first()

        enable_email = (enable_set.value.lower() == 'true') if enable_set and enable_set.value else getattr(Config, 'ENABLE_EMAIL_ALERTS', True)
        email_mode = mode_set.value.upper() if mode_set and mode_set.value else getattr(Config, 'EMAIL_MODE', 'API').upper()
        email_provider = provider_set.value.upper() if provider_set and provider_set.value else getattr(Config, 'EMAIL_PROVIDER', 'RESEND').upper()
        email_api_key = api_key_set.value if api_key_set and api_key_set.value else getattr(Config, 'EMAIL_API_KEY', '')
        email_from = from_set.value if from_set and from_set.value else getattr(Config, 'EMAIL_FROM', getattr(Config, 'GMAIL_EMAIL', 'onboarding@resend.dev'))
        
        gmail_email = gmail_set.value if gmail_set and gmail_set.value else getattr(Config, 'GMAIL_EMAIL', '')
        gmail_app_password = pass_set.value if pass_set and pass_set.value else getattr(Config, 'GMAIL_APP_PASSWORD', '')

        if email_mode == 'API':
            has_credentials = bool(email_api_key and email_from)
        else:
            has_credentials = bool(gmail_email and gmail_app_password)

        return {
            'enable_email_alerts': enable_email,
            'email_mode': email_mode,
            'email_provider': email_provider,
            'email_api_key': email_api_key,
            'email_from': email_from,
            'gmail_email': gmail_email,
            'gmail_app_password': gmail_app_password,
            'smtp_server': getattr(Config, 'SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': getattr(Config, 'SMTP_PORT', 587),
            'has_credentials': has_credentials
        }
    except Exception:
        email_mode = getattr(Config, 'EMAIL_MODE', 'API').upper()
        email_api_key = getattr(Config, 'EMAIL_API_KEY', '')
        email_from = getattr(Config, 'EMAIL_FROM', getattr(Config, 'GMAIL_EMAIL', 'onboarding@resend.dev'))
        gmail_email = getattr(Config, 'GMAIL_EMAIL', '')
        gmail_app_password = getattr(Config, 'GMAIL_APP_PASSWORD', '')

        if email_mode == 'API':
            has_credentials = bool(email_api_key and email_from)
        else:
            has_credentials = bool(gmail_email and gmail_app_password)

        return {
            'enable_email_alerts': getattr(Config, 'ENABLE_EMAIL_ALERTS', True),
            'email_mode': email_mode,
            'email_provider': getattr(Config, 'EMAIL_PROVIDER', 'RESEND').upper(),
            'email_api_key': email_api_key,
            'email_from': email_from,
            'gmail_email': gmail_email,
            'gmail_app_password': gmail_app_password,
            'smtp_server': getattr(Config, 'SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': getattr(Config, 'SMTP_PORT', 587),
            'has_credentials': has_credentials
        }

def _record_email_log(session_id, student_id, student_name, roll_no, parent_email, session_title, subject, body, status):
    """
    Persists Email log entry in database.
    """
    try:
        from models import db, EmailLog
        log_entry = EmailLog(
            session_id=session_id,
            student_id=student_id,
            student_name=student_name,
            roll_no=roll_no,
            parent_email=parent_email,
            session_title=session_title,
            subject=subject,
            body=body,
            status=status
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to save email log: {e}")

def _send_via_https_api(to_email, subject, body_text, conf):
    """
    Dispatches transactional email via HTTPS REST API (Port 443).
    Bypasses Render Free SMTP port blocks completely.
    Supports RESEND, BREVO, and SENDGRID.
    """
    import requests

    provider = conf['email_provider']
    api_key = conf['email_api_key']
    email_from = conf['email_from']
    masked_target = mask_email(to_email)

    if not api_key:
        err_msg = f"HTTPS Email API key missing for provider {provider}."
        logger.warning(f"[EMAIL_API] {err_msg}")
        return False, err_msg

    logger.info(f"[EMAIL_API] Preparing HTTPS POST request for provider={provider} target={masked_target}")

    try:
        if provider == 'BREVO':
            url = "https://api.brevo.com/v3/smtp/email"
            headers = {
                "api-key": api_key,
                "Content-Type": "application/json",
                "Accept": "application/json"
            }
            payload = {
                "sender": {"email": email_from, "name": "AI Attendance System"},
                "to": [{"email": to_email}],
                "subject": subject,
                "textContent": body_text
            }
        elif provider == 'SENDGRID':
            url = "https://api.sendgrid.com/v3/mail/send"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "personalizations": [{"to": [{"email": to_email}]}],
                "from": {"email": email_from, "name": "AI Attendance System"},
                "subject": subject,
                "content": [{"type": "text/plain", "value": body_text}]
            }
        else:
            # Default to RESEND (https://api.resend.com/emails)
            url = "https://api.resend.com/emails"
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            payload = {
                "from": email_from if ("@" in email_from) else "onboarding@resend.dev",
                "to": [to_email],
                "subject": subject,
                "text": body_text
            }

        response = requests.post(url, headers=headers, json=payload, timeout=10)

        if response.status_code in (200, 201, 202):
            logger.info(f"[EMAIL_API] Message accepted by {provider} API for {masked_target} (HTTP {response.status_code})")
            return True, f"Email sent successfully via {provider} HTTPS API."
        else:
            # Parse error summary without exposing secrets
            try:
                err_json = response.json()
                err_detail = err_json.get('message') or err_json.get('error') or response.text[:150]
            except Exception:
                err_detail = response.text[:150]
            err_msg = f"{provider} API returned HTTP {response.status_code}: {err_detail}"
            logger.error(f"[EMAIL_API] Failed for {masked_target}: {err_msg}")
            return False, err_msg

    except requests.RequestException as req_err:
        err_msg = f"{provider} HTTPS network request failed: {str(req_err)}"
        logger.error(f"[EMAIL_API] Network error for {masked_target}: {err_msg}")
        return False, err_msg
    except Exception as ex:
        err_msg = f"Unexpected error during HTTPS email dispatch: {str(ex)}"
        logger.error(f"[EMAIL_API] Exception for {masked_target}: {err_msg}")
        return False, err_msg

def _send_via_smtp(to_email, subject, body_text, conf):
    """
    Sends email notification via Gmail SMTP (local development only).
    """
    masked_target = mask_email(to_email)
    try:
        msg_mime = MIMEMultipart()
        msg_mime['From'] = f"AI Attendance System <{conf['gmail_email']}>"
        msg_mime['To'] = to_email
        msg_mime['Subject'] = subject
        msg_mime.attach(MIMEText(body_text, 'plain'))

        logger.info(f"[GMAIL_SMTP] Local SMTP connection started for {masked_target}")
        server = smtplib.SMTP(conf['smtp_server'], conf['smtp_port'], timeout=12)
        server.starttls()
        server.login(conf['gmail_email'], conf['gmail_app_password'])
        server.send_message(msg_mime)
        server.quit()

        logger.info(f"[GMAIL_SMTP] Email accepted for {masked_target}")
        return True, f"Parent email sent successfully to {masked_target} via local SMTP"
    except smtplib.SMTPAuthenticationError:
        err_msg = "Gmail authentication failed."
        logger.error(f"[GMAIL_SMTP] Email failed: {err_msg} for {masked_target}")
        return False, err_msg
    except smtplib.SMTPConnectError:
        err_msg = "Gmail SMTP connection failed."
        logger.error(f"[GMAIL_SMTP] Email failed: {err_msg}")
        return False, err_msg
    except Exception as e:
        err_msg = f"Gmail SMTP connection failed: {str(e)}"
        logger.error(f"[GMAIL_SMTP] Email failed: {err_msg} for {masked_target}")
        return False, err_msg

def send_parent_absent_email(parent_email, student_name, roll_no, class_name, date_str, teacher_name='Professor', session_title='Session', session_id=None, student_id=None, force_test=False):
    """
    Sends an automated parent absence email notification via HTTPS API (Render Production)
    or local Gmail SMTP (local dev mode).
    Does NOT log or expose API keys or passwords.
    """
    if not validate_email_address(parent_email):
        msg = "Invalid recipient email."
        logger.warning(f"[EMAIL] Email failed: {msg} ({parent_email})")
        return False, msg

    conf = get_email_config()

    if not force_test and not conf['enable_email_alerts']:
        msg = "Email alerts are disabled in system settings."
        logger.info(f"[EMAIL] Email disabled: {msg}")
        return False, msg

    subject = f"Attendance Alert - {student_name} Marked Absent"
    body_text = (
        f"Dear Parent,\n\n"
        f"This is to inform you that your child was marked ABSENT.\n\n"
        f"Student Name: {student_name}\n"
        f"Roll Number: {roll_no}\n"
        f"Class: {class_name}\n"
        f"Date: {date_str}\n"
        f"Attendance Status: ABSENT\n\n"
        f"Please contact the institution if this absence is unexpected.\n\n"
        f"Regards,\n"
        f"AI Group Attendance System"
    )

    masked_target = mask_email(parent_email)

    if not conf['has_credentials']:
        msg = f"Email credentials for mode={conf['email_mode']} are missing."
        logger.warning(f"[EMAIL] Email failed: {msg} for {masked_target}")
        _record_email_log(session_id, student_id, student_name, roll_no, parent_email, session_title, subject, body_text, 'FAILED')
        return False, msg

    if conf['email_mode'] == 'API':
        success, msg = _send_via_https_api(parent_email, subject, body_text, conf)
    else:
        success, msg = _send_via_smtp(parent_email, subject, body_text, conf)

    status = 'SENT' if success else 'FAILED'
    _record_email_log(session_id, student_id, student_name, roll_no, parent_email, session_title, subject, body_text, status)
    
    if success:
        return True, "Test email sent successfully." if force_test else f"Parent email sent successfully to {masked_target}"
    else:
        return False, msg

def send_test_email(target_email, teacher_name='Admin'):
    """
    Sends a test email notification to verify HTTPS API or local SMTP configuration.
    """
    if not validate_email_address(target_email):
        return False, "Invalid recipient email."

    conf = get_email_config()
    if not conf['has_credentials']:
        return False, f"Email credentials for mode={conf['email_mode']} are missing."

    subject = "AI Group Attendance System - Test Email"
    body_text = "This is a test email from the AI Group Attendance System."
    masked_target = mask_email(target_email)

    if conf['email_mode'] == 'API':
        success, msg = _send_via_https_api(target_email, subject, body_text, conf)
    else:
        success, msg = _send_via_smtp(target_email, subject, body_text, conf)

    status = 'SENT' if success else 'FAILED'
    _record_email_log(None, None, "Test Student", "TEST001", target_email, "Admin Test", subject, body_text, status)
    return success, msg
