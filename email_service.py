import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import logging
from datetime import datetime
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("EmailService")

def get_smtp_config():
    """
    Retrieves SMTP settings from DB SystemSetting table or Config fallback.
    """
    try:
        from models import db, SystemSetting
        email_set = SystemSetting.query.filter_by(key='smtp_email').first()
        pass_set = SystemSetting.query.filter_by(key='smtp_password').first()
        enable_set = SystemSetting.query.filter_by(key='enable_real_email').first()

        smtp_email = email_set.value if email_set and email_set.value else Config.SMTP_EMAIL
        smtp_password = pass_set.value if pass_set and pass_set.value else Config.SMTP_PASSWORD
        enable_real = (enable_set.value.lower() == 'true') if enable_set and enable_set.value else Config.ENABLE_REAL_EMAIL

        return {
            'smtp_server': Config.SMTP_SERVER,
            'smtp_port': Config.SMTP_PORT,
            'smtp_email': smtp_email,
            'smtp_password': smtp_password,
            'enable_real_email': enable_real
        }
    except Exception as e:
        return {
            'smtp_server': Config.SMTP_SERVER,
            'smtp_port': Config.SMTP_PORT,
            'smtp_email': Config.SMTP_EMAIL,
            'smtp_password': Config.SMTP_PASSWORD,
            'enable_real_email': Config.ENABLE_REAL_EMAIL
        }

def send_parent_absent_email(parent_email, student_name, roll_no, class_name, date_str, teacher_name, student_code='N/A', session_title='Class Lecture', force_test=False):
    """
    Sends an automated HTML email alert to the parent notifying them of their child's absence.
    Uses 100% inline styles to guarantee ultra-high text visibility across all email clients.
    """
    subject = f"⚠️ Absence Alert: {student_name} ({roll_no}) - {class_name}"
    
    # Format teacher name cleanly without duplicating 'Prof.'
    formatted_teacher = teacher_name if teacher_name.startswith("Prof") else f"Prof. {teacher_name}"

    html_body = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
    </head>
    <body style="font-family: Arial, 'Segoe UI', sans-serif; background-color: #f1f5f9; color: #1e293b; margin: 0; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto; background-color: #ffffff; border-radius: 12px; padding: 30px; border: 1px solid #cbd5e1; box-shadow: 0 10px 25px rgba(0,0,0,0.1);">
            
            <div style="text-align: center; border-bottom: 2px solid #ef4444; padding-bottom: 15px; margin-bottom: 20px;">
                <h2 style="color: #dc2626; margin: 0; font-size: 24px; font-weight: bold;">Automated Attendance Notice</h2>
            </div>
            
            <p style="color: #334155; font-size: 15px; line-height: 1.5; margin: 0 0 10px 0;">Dear Parent / Guardian,</p>
            <p style="color: #334155; font-size: 15px; line-height: 1.5; margin: 0 0 20px 0;">This is an automated notification from the <strong style="color: #0f172a;">Smart AI Attendance System</strong> regarding your ward's attendance today.</p>
            
            <div style="background-color: #f8fafc; padding: 20px; border-radius: 8px; border-left: 5px solid #dc2626; margin: 20px 0; border-top: 1px solid #e2e8f0; border-right: 1px solid #e2e8f0; border-bottom: 1px solid #e2e8f0;">
                <table style="width: 100%; border-collapse: collapse;">
                    <tr>
                        <td style="padding: 8px 0; font-size: 14px; color: #475569; font-weight: bold; width: 40%;">Student Name:</td>
                        <td style="padding: 8px 0; font-size: 15px; color: #0f172a; font-weight: bold;">{student_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-size: 14px; color: #475569; font-weight: bold;">Roll Number:</td>
                        <td style="padding: 8px 0; font-size: 14px; color: #0f172a; font-weight: bold;">{roll_no}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-size: 14px; color: #475569; font-weight: bold;">Class / Section:</td>
                        <td style="padding: 8px 0; font-size: 14px; color: #0f172a; font-weight: bold;">{class_name}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-size: 14px; color: #475569; font-weight: bold;">Session / Lecture:</td>
                        <td style="padding: 8px 0; font-size: 14px; color: #0f172a; font-weight: bold;">{session_title}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-size: 14px; color: #475569; font-weight: bold;">Attendance Status:</td>
                        <td style="padding: 8px 0;">
                            <span style="display: inline-block; background-color: #dc2626; color: #ffffff; padding: 4px 14px; border-radius: 20px; font-weight: bold; font-size: 13px;">ABSENT</span>
                        </td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-size: 14px; color: #475569; font-weight: bold;">Date & Time:</td>
                        <td style="padding: 8px 0; font-size: 14px; color: #0f172a; font-weight: bold;">{date_str}</td>
                    </tr>
                    <tr>
                        <td style="padding: 8px 0; font-size: 14px; color: #475569; font-weight: bold;">Recorded By:</td>
                        <td style="padding: 8px 0; font-size: 14px; color: #0f172a; font-weight: bold;">{formatted_teacher}</td>
                    </tr>
                </table>
            </div>

            <p style="color: #475569; font-size: 14px; line-height: 1.5; margin: 20px 0 0 0;">Please contact the class teacher or school administration if you believe this is an error or need to provide leave justification.</p>
            
            <div style="text-align: center; margin-top: 30px; font-size: 12px; color: #64748b; border-top: 1px solid #e2e8f0; padding-top: 15px;">
                <p style="margin: 0 0 5px 0;">&copy; {datetime.now().year} Smart Group Attendance System. All rights reserved.</p>
                <p style="margin: 0;">This is a system-generated message. Please do not reply directly to this email.</p>
            </div>
        </div>
    </body>
    </html>
    """

    conf = get_smtp_config()

    if not force_test and not conf['enable_real_email']:
        msg = "Real email delivery is currently disabled. Open SMTP Email Settings and check 'Enable Real Parent Email Delivery'."
        logger.info(f"[EMAIL SIMULATED] {msg}")
        return False, msg

    if not conf['smtp_password']:
        msg = "Gmail App Password missing. Please set your 16-character Gmail App Password in SMTP Email Settings."
        logger.warning(f"[EMAIL CONFIG ERROR] {msg}")
        return False, msg

    try:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"AI Attendance System <{conf['smtp_email']}>"
        msg["To"] = parent_email
        msg.attach(MIMEText(html_body, "html"))

        with smtplib.SMTP(conf['smtp_server'], conf['smtp_port']) as server:
            server.starttls()
            server.login(conf['smtp_email'], conf['smtp_password'])
            server.sendmail(conf['smtp_email'], parent_email, msg.as_string())
            
        logger.info(f"REAL EMAIL SENT successfully to {parent_email} for student {student_name}")
        return True, f"Real email delivered to {parent_email}"
    except Exception as e:
        err_msg = str(e)
        logger.error(f"Failed to send email via SMTP to {parent_email}: {err_msg}")
        return False, f"Gmail SMTP Error: {err_msg}"
