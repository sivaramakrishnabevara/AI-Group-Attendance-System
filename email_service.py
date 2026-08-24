import os
import smtplib
import re
import logging
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

def get_email_config():
    """
    Retrieves Email settings from DB SystemSetting table or Config fallback.
    """
    try:
        from models import SystemSetting
        
        enable_set = SystemSetting.query.filter_by(key='enable_email_alerts').first()
        gmail_set = SystemSetting.query.filter_by(key='gmail_email').first()
        pass_set = SystemSetting.query.filter_by(key='gmail_app_password').first()

        enable_email = (enable_set.value.lower() == 'true') if enable_set and enable_set.value else getattr(Config, 'ENABLE_EMAIL_ALERTS', True)
        gmail_email = gmail_set.value if gmail_set and gmail_set.value else getattr(Config, 'GMAIL_EMAIL', '')
        gmail_app_password = pass_set.value if pass_set and pass_set.value else getattr(Config, 'GMAIL_APP_PASSWORD', '')

        return {
            'enable_email_alerts': enable_email,
            'gmail_email': gmail_email,
            'gmail_app_password': gmail_app_password,
            'smtp_server': getattr(Config, 'SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': getattr(Config, 'SMTP_PORT', 587),
            'has_credentials': bool(gmail_email and gmail_app_password)
        }
    except Exception:
        return {
            'enable_email_alerts': getattr(Config, 'ENABLE_EMAIL_ALERTS', True),
            'gmail_email': getattr(Config, 'GMAIL_EMAIL', ''),
            'gmail_app_password': getattr(Config, 'GMAIL_APP_PASSWORD', ''),
            'smtp_server': getattr(Config, 'SMTP_SERVER', 'smtp.gmail.com'),
            'smtp_port': getattr(Config, 'SMTP_PORT', 587),
            'has_credentials': bool(getattr(Config, 'GMAIL_EMAIL', '') and getattr(Config, 'GMAIL_APP_PASSWORD', ''))
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

def send_parent_absent_email(parent_email, student_name, roll_no, class_name, date_str, teacher_name='Teacher', session_title='Session', session_id=None, student_id=None, force_test=False):
    """
    Sends an automated parent absence email notification via Gmail SMTP (smtp.gmail.com:587 TLS).
    Does NOT log or expose Google App Passwords.
    """
    if not validate_email_address(parent_email):
        msg = f"Invalid parent email address syntax: {parent_email}"
        logger.warning(f"[EMAIL FAILED] {msg}")
        return False, msg

    conf = get_email_config()

    if not force_test and not conf['enable_email_alerts']:
        msg = "Email alerts are disabled in system settings."
        logger.info(f"[EMAIL DISABLED] {msg}")
        return False, msg

    subject = f"Attendance Alert - {student_name} Marked Absent"
    body_text = (
        f"Dear Parent,\n\n"
        f"This is to inform you that your child:\n"
        f"  Student Name: {student_name}\n"
        f"  Roll Number: {roll_no}\n"
        f"  Class: {class_name}\n"
        f"  Date: {date_str}\n"
        f"  Attendance Status: ABSENT\n\n"
        f"Your child was marked absent during today's attendance session.\n"
        f"Please contact the institution if this absence is unexpected.\n\n"
        f"Regards,\n"
        f"AI Group Attendance System"
    )

    masked_target = mask_email(parent_email)

    if not conf['has_credentials']:
        msg = "Gmail SMTP is not configured."
        logger.warning(f"[EMAIL CONFIG ERROR] Gmail credentials missing for target {masked_target}")
        _record_email_log(session_id, student_id, student_name, roll_no, parent_email, session_title, subject, body_text, 'FAILED')
        return False, msg

    try:
        msg_mime = MIMEMultipart()
        msg_mime['From'] = f"AI Attendance System <{conf['gmail_email']}>"
        msg_mime['To'] = parent_email
        msg_mime['Subject'] = subject
        msg_mime.attach(MIMEText(body_text, 'plain'))

        server = smtplib.SMTP(conf['smtp_server'], conf['smtp_port'], timeout=12)
        server.starttls()
        server.login(conf['gmail_email'], conf['gmail_app_password'])
        server.send_message(msg_mime)
        server.quit()

        logger.info(f"[EMAIL SUCCESS] Parent email sent successfully to {masked_target}")
        _record_email_log(session_id, student_id, student_name, roll_no, parent_email, session_title, subject, body_text, 'SENT')
        return True, f"Parent email sent successfully to {masked_target}"

    except smtplib.SMTPAuthenticationError:
        err_msg = "Gmail authentication failed. Please check GMAIL_EMAIL and GMAIL_APP_PASSWORD."
        logger.error(f"[EMAIL FAILED] {err_msg} for {masked_target}")
        _record_email_log(session_id, student_id, student_name, roll_no, parent_email, session_title, subject, body_text, 'FAILED')
        return False, err_msg
    except smtplib.SMTPConnectError:
        err_msg = "Gmail SMTP connection failed. Please check network connection or SMTP port 587."
        logger.error(f"[EMAIL FAILED] {err_msg}")
        _record_email_log(session_id, student_id, student_name, roll_no, parent_email, session_title, subject, body_text, 'FAILED')
        return False, err_msg
    except Exception as e:
        err_msg = f"Parent email failed: {str(e)}"
        logger.error(f"[EMAIL FAILED] {err_msg} for {masked_target}")
        _record_email_log(session_id, student_id, student_name, roll_no, parent_email, session_title, subject, body_text, 'FAILED')
        return False, err_msg

def send_test_email(target_email, teacher_name='Admin'):
    """
    Sends a test email notification to verify Gmail SMTP configuration.
    """
    conf = get_email_config()
    if not conf['has_credentials']:
        return False, "Gmail SMTP is not configured."

    subject = "AI Group Attendance System - Test Email"
    body_text = "This is a test email from the AI Group Attendance System."
    masked_target = mask_email(target_email)

    try:
        msg_mime = MIMEMultipart()
        msg_mime['From'] = f"AI Attendance System <{conf['gmail_email']}>"
        msg_mime['To'] = target_email
        msg_mime['Subject'] = subject
        msg_mime.attach(MIMEText(body_text, 'plain'))

        server = smtplib.SMTP(conf['smtp_server'], conf['smtp_port'], timeout=12)
        server.starttls()
        server.login(conf['gmail_email'], conf['gmail_app_password'])
        server.send_message(msg_mime)
        server.quit()

        logger.info(f"[TEST EMAIL SUCCESS] Test email sent successfully to {masked_target}")
        _record_email_log(None, None, "Test Student", "TEST001", target_email, "Admin Test", subject, body_text, 'SENT')
        return True, f"Test email sent successfully to {masked_target}"
    except smtplib.SMTPAuthenticationError:
        err_msg = "Gmail authentication failed. Please check GMAIL_EMAIL and GMAIL_APP_PASSWORD."
        logger.error(f"[TEST EMAIL FAILED] {err_msg}")
        _record_email_log(None, None, "Test Student", "TEST001", target_email, "Admin Test", subject, body_text, 'FAILED')
        return False, err_msg
    except Exception as e:
        err_msg = f"Gmail SMTP connection failed: {str(e)}"
        logger.error(f"[TEST EMAIL FAILED] {err_msg}")
        _record_email_log(None, None, "Test Student", "TEST001", target_email, "Admin Test", subject, body_text, 'FAILED')
        return False, err_msg
