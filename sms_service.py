import os
import json
import logging
import urllib.request
import urllib.parse
import re
from datetime import datetime
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("SMSService")

def normalize_indian_mobile(phone):
    """
    Validates and normalizes Indian mobile numbers safely.
    Accepts formats: 9876543210, +919876543210, 09876543210, 919876543210
    Returns: (is_valid: bool, formatted_number: str)
    """
    if not phone:
        return False, ""
    
    # Clean non-digit characters except leading +
    cleaned = re.sub(r'[^\d+]', '', str(phone).strip())
    
    # Strip leading + or 0
    digits = cleaned.lstrip('+')
    if digits.startswith('0'):
        digits = digits[1:]
    
    if len(digits) == 12 and digits.startswith('91'):
        digits = digits[2:]
        
    # Check valid 10-digit Indian mobile number starting with 6, 7, 8, 9
    if len(digits) == 10 and digits[0] in ['6', '7', '8', '9']:
        return True, f"+91{digits}"
    
    # Generic international fallback if length is valid (10-15 digits)
    if 10 <= len(digits) <= 15:
        prefix = '+' if cleaned.startswith('+') else '+91' if len(digits) == 10 else '+'
        return True, f"{prefix}{digits}"
        
    return False, phone

def mask_phone_number(phone):
    """
    Masks phone number for secure display (e.g. +91 98******10).
    Never exposes complete mobile numbers in public logs.
    """
    if not phone or len(str(phone)) < 8:
        return "********"
    valid, norm = normalize_indian_mobile(phone)
    if not valid:
        return "*****" + str(phone)[-4:]
    return norm[:5] + "******" + norm[-2:]

def get_sms_config():
    """
    Retrieves SMS settings from DB SystemSetting table or Config fallback.
    Supports both 'SIMULATION' and 'REAL_SMS' operating modes.
    """
    try:
        from models import SystemSetting
        
        mode_set = SystemSetting.query.filter_by(key='sms_mode').first()
        provider_set = SystemSetting.query.filter_by(key='sms_provider').first()
        key_set = SystemSetting.query.filter_by(key='sms_api_key').first()
        secret_set = SystemSetting.query.filter_by(key='sms_api_secret').first()
        sender_set = SystemSetting.query.filter_by(key='sms_sender_id').first()
        enable_set = SystemSetting.query.filter_by(key='sms_enabled').first()
        url_set = SystemSetting.query.filter_by(key='sms_http_url').first()
        route_set = SystemSetting.query.filter_by(key='sms_route').first()
        dlt_te_set = SystemSetting.query.filter_by(key='sms_dlt_te_id').first()

        sms_mode = (mode_set.value.upper() if mode_set and mode_set.value else getattr(Config, 'SMS_MODE', 'SIMULATION')).upper()
        sms_provider = provider_set.value if provider_set and provider_set.value else getattr(Config, 'SMS_PROVIDER', 'GENERIC_HTTP')
        sms_api_key = key_set.value if key_set and key_set.value else getattr(Config, 'SMS_API_KEY', '')
        sms_api_secret = secret_set.value if secret_set and secret_set.value else getattr(Config, 'SMS_API_SECRET', '')
        sms_sender_id = sender_set.value if sender_set and sender_set.value else getattr(Config, 'SMS_SENDER_ID', 'ATTNDS')
        sms_http_url = url_set.value if url_set and url_set.value else getattr(Config, 'SMS_HTTP_URL', '')
        sms_enabled = (enable_set.value.lower() == 'true') if enable_set and enable_set.value else getattr(Config, 'SMS_ENABLED', True)
        sms_route = route_set.value if route_set and route_set.value else getattr(Config, 'SMS_ROUTE', 'q')
        sms_dlt_te_id = dlt_te_set.value if dlt_te_set and dlt_te_set.value else getattr(Config, 'SMS_DLT_TE_ID', '')

        return {
            'sms_mode': sms_mode, # 'SIMULATION' or 'REAL_SMS'
            'sms_provider': sms_provider.upper(),
            'sms_api_key': sms_api_key,
            'sms_api_secret': sms_api_secret,
            'sms_sender_id': sms_sender_id,
            'sms_http_url': sms_http_url,
            'sms_enabled': sms_enabled,
            'sms_route': sms_route.lower(),
            'sms_dlt_te_id': sms_dlt_te_id,
            'has_api_key': bool(sms_api_key)
        }
    except Exception:
        return {
            'sms_mode': getattr(Config, 'SMS_MODE', 'SIMULATION').upper(),
            'sms_provider': getattr(Config, 'SMS_PROVIDER', 'GENERIC_HTTP').upper(),
            'sms_api_key': getattr(Config, 'SMS_API_KEY', ''),
            'sms_api_secret': getattr(Config, 'SMS_API_SECRET', ''),
            'sms_sender_id': getattr(Config, 'SMS_SENDER_ID', 'ATTNDS'),
            'sms_http_url': getattr(Config, 'SMS_HTTP_URL', ''),
            'sms_enabled': getattr(Config, 'SMS_ENABLED', True),
            'sms_route': getattr(Config, 'SMS_ROUTE', 'q').lower(),
            'sms_dlt_te_id': getattr(Config, 'SMS_DLT_TE_ID', ''),
            'has_api_key': bool(getattr(Config, 'SMS_API_KEY', ''))
        }

def _parse_fast2sms_error(api_msg, route, sender_id):
    """
    Parses Fast2SMS API response messages and returns clear error diagnostics.
    """
    msg_lower = str(api_msg).lower()

    if 'dnd' in msg_lower:
        return (
            f"Fast2SMS DND Blocked: Target phone number is registered on DND (Do Not Disturb). "
            f"Quick SMS route ('q') cannot deliver to DND numbers in India. "
            f"To deliver alerts to DND numbers, set SMS_ROUTE=dlt (with DLT Template ID) or SMS_ROUTE=otp."
        )
    elif 'balance' in msg_lower or 'insufficient' in msg_lower or '412' in msg_lower:
        return "Fast2SMS Error: Insufficient wallet balance. Please top up your Fast2SMS wallet balance."
    elif 'authorization' in msg_lower or 'invalid' in msg_lower and 'key' in msg_lower or '401' in msg_lower:
        return "Fast2SMS Error: Invalid Authorization API Key. Please check SMS_API_KEY in environment variables."
    elif 'sender' in msg_lower or '411' in msg_lower:
        return f"Fast2SMS Error: Invalid Sender ID ('{sender_id}'). Ensure Sender ID is approved on DLT portal and registered in Fast2SMS."
    elif 'route' in msg_lower or 'dlt' in msg_lower or 'template' in msg_lower:
        return f"Fast2SMS Error: DLT Template / Route rejected ('{route}'). Check SMS_ROUTE and SMS_DLT_TE_ID."
    else:
        return f"Fast2SMS Error: {api_msg}"

def _record_sms_log(session_id, student_id, student_name, roll_no, parent_mobile, session_title, message, status, mode):
    """
    Persists SMS notification log entry into database for Admin audit trail.
    """
    try:
        from models import db, SMSLog
        log_entry = SMSLog(
            session_id=session_id,
            student_id=student_id,
            student_name=student_name,
            roll_no=roll_no,
            parent_mobile=parent_mobile,
            session_title=session_title,
            message=message,
            status=status,
            mode=mode
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        logger.error(f"Failed to save SMS log: {e}")

def send_parent_absent_sms(parent_mobile, student_name, roll_no, class_name, date_str, teacher_name='Teacher', session_title='Session', session_id=None, student_id=None, force_test=False):
    """
    Unified entrypoint for parent absence notification.
    Handles both SIMULATION mode and REAL_SMS mode cleanly.
    Never prints API keys or secrets in logs.
    """
    is_valid, norm_phone = normalize_indian_mobile(parent_mobile)
    if not is_valid:
        msg = f"Invalid parent mobile number format: {parent_mobile}"
        logger.warning(f"[SMS FAILED] {msg}")
        return False, msg

    sms_text = f"Dear Parent, your child {student_name} (Roll No: {roll_no}) was marked ABSENT for today's attendance on {date_str}. Please contact the institution if unexpected."
    conf = get_sms_config()
    sms_mode = conf.get('sms_mode', 'SIMULATION')

    # =========================================================================
    # MODE 1: FREE SIMULATION MODE
    # =========================================================================
    if sms_mode == 'SIMULATION':
        masked_num = mask_phone_number(norm_phone)
        logger.info(
            f"[SMS SIMULATED SUCCESSFULLY]\n"
            f"  Recipient: {masked_num}\n"
            f"  Student: {student_name} ({roll_no})\n"
            f"  Status: SIMULATED\n"
            f"  Mode: SIMULATION\n"
            f"  Message: {sms_text}"
        )

        _record_sms_log(
            session_id=session_id,
            student_id=student_id,
            student_name=student_name,
            roll_no=roll_no,
            parent_mobile=norm_phone,
            session_title=session_title,
            message=sms_text,
            status='SIMULATED',
            mode='SIMULATION'
        )

        return True, f"SMS simulated successfully for {student_name} ({masked_num})."

    # =========================================================================
    # MODE 2: REAL SMS MODE (Executes Actual External API Call)
    # =========================================================================
    if not force_test and not conf['sms_enabled']:
        msg = "SMS service is disabled in settings."
        logger.info(f"[SMS DISABLED] {msg}")
        return False, msg

    if not conf['sms_api_key'] and not conf['sms_http_url']:
        msg = "SMS service API credentials missing for REAL_SMS mode."
        logger.info(f"[SMS CONFIG ERROR] {msg}")
        return False, msg

    provider = conf['sms_provider']
    masked_phone = mask_phone_number(norm_phone)

    logger.info(f"[SMS API REQUEST ATTEMPTED] Mode: REAL_SMS | Provider: {provider} | Target: {masked_phone}")

    try:
        # ---- PROVIDER 1: Fast2SMS (India) ----
        if provider == 'FAST2SMS':
            route = (conf.get('sms_route') or 'q').lower()
            sender_id = conf.get('sms_sender_id') or 'ATTNDS'
            dlt_template_id = conf.get('sms_dlt_te_id') or ''
            phone_number = norm_phone.replace('+91', '')

            if route == 'dlt':
                payload_dict = {
                    "route": "dlt",
                    "sender_id": sender_id,
                    "message": dlt_template_id if dlt_template_id else sms_text,
                    "variables_values": f"{student_name}|{roll_no}|{date_str}",
                    "flash": 0,
                    "numbers": phone_number
                }
            elif route == 'otp':
                payload_dict = {
                    "route": "otp",
                    "variables_values": sms_text,
                    "numbers": phone_number
                }
            else:
                payload_dict = {
                    "route": "q",
                    "message": sms_text,
                    "language": "english",
                    "flash": 0,
                    "numbers": phone_number
                }
                if sender_id and sender_id != 'ATTNDS':
                    payload_dict["sender_id"] = sender_id

            payload = json.dumps(payload_dict).encode('utf-8')
            req = urllib.request.Request("https://www.fast2sms.com/dev/bulkV2", data=payload, headers={
                "authorization": conf['sms_api_key'],
                "Content-Type": "application/json"
            })

            with urllib.request.urlopen(req, timeout=10) as response:
                res_raw = response.read().decode('utf-8')
                res_json = json.loads(res_raw)

                if res_json.get('return') == True or res_json.get('status_code') == 200:
                    logger.info(f"[SMS ACCEPTED BY PROVIDER] Fast2SMS ({route.upper()}) accepted message for {masked_phone}")
                    _record_sms_log(session_id, student_id, student_name, roll_no, norm_phone, session_title, sms_text, 'SENT', 'REAL_SMS')
                    return True, f"SMS sent successfully to {masked_phone}"
                else:
                    api_msg = str(res_json.get('message') or res_json)
                    parsed_err = _parse_fast2sms_error(api_msg, route, sender_id)
                    logger.error(f"[SMS FAILED] Provider Fast2SMS failed for {masked_phone}: {parsed_err}")
                    _record_sms_log(session_id, student_id, student_name, roll_no, norm_phone, session_title, sms_text, 'FAILED', 'REAL_SMS')
                    return False, parsed_err

        # ---- PROVIDER 2: Twilio ----
        elif provider == 'TWILIO':
            account_sid = conf['sms_api_key']
            auth_token = conf['sms_api_secret']
            from_number = conf['sms_sender_id']
            
            url = f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json"
            data = urllib.parse.urlencode({
                'To': norm_phone,
                'From': from_number,
                'Body': sms_text
            }).encode('utf-8')

            import base64
            auth_header = "Basic " + base64.b64encode(f"{account_sid}:{auth_token}".encode('utf-8')).decode('utf-8')
            req = urllib.request.Request(url, data=data, headers={
                "Authorization": auth_header,
                "Content-Type": "application/x-www-form-urlencoded"
            })
            with urllib.request.urlopen(req, timeout=10) as response:
                logger.info(f"[SMS ACCEPTED BY PROVIDER] Twilio accepted message for {masked_phone}")
                _record_sms_log(session_id, student_id, student_name, roll_no, norm_phone, session_title, sms_text, 'SENT', 'REAL_SMS')
                return True, f"SMS sent successfully to {masked_phone}"

        # ---- PROVIDER 3: MSG91 ----
        elif provider == 'MSG91':
            payload = json.dumps({
                "sender": conf['sms_sender_id'],
                "route": "4",
                "country": "91",
                "sms": [{"message": sms_text, "to": [norm_phone.replace('+91', '')]}]
            }).encode('utf-8')
            req = urllib.request.Request("https://api.msg91.com/api/v2/sendsms", data=payload, headers={
                "authkey": conf['sms_api_key'],
                "content-type": "application/json"
            })
            with urllib.request.urlopen(req, timeout=10) as response:
                logger.info(f"[SMS ACCEPTED BY PROVIDER] MSG91 accepted message for {masked_phone}")
                _record_sms_log(session_id, student_id, student_name, roll_no, norm_phone, session_title, sms_text, 'SENT', 'REAL_SMS')
                return True, f"SMS sent successfully to {masked_phone}"

        # ---- PROVIDER 4: Generic HTTP Webhook Gateway ----
        else:
            http_url = conf['sms_http_url'] or "https://api.sms-gateway.example/send"
            data = urllib.parse.urlencode({
                'api_key': conf['sms_api_key'],
                'sender': conf['sms_sender_id'],
                'to': norm_phone,
                'message': sms_text
            }).encode('utf-8')
            req = urllib.request.Request(http_url, data=data, headers={
                "Content-Type": "application/x-www-form-urlencoded"
            })
            with urllib.request.urlopen(req, timeout=10) as response:
                logger.info(f"[SMS ACCEPTED BY PROVIDER] Generic HTTP Gateway accepted message for {masked_phone}")
                _record_sms_log(session_id, student_id, student_name, roll_no, norm_phone, session_title, sms_text, 'SENT', 'REAL_SMS')
                return True, f"SMS sent successfully to {masked_phone}"

    except Exception as e:
        err_msg = str(e)
        logger.error(f"[SMS FAILED] Provider {provider} failed for {masked_phone}: {err_msg}")
        _record_sms_log(session_id, student_id, student_name, roll_no, norm_phone, session_title, sms_text, 'FAILED', 'REAL_SMS')
        return False, f"SMS Gateway Error: {err_msg}"

def send_test_sms(target_phone, teacher_name='Admin'):
    """
    Sends a test SMS notification.
    """
    return send_parent_absent_sms(
        parent_mobile=target_phone,
        student_name="Test Student",
        roll_no="TEST001",
        class_name="Test Class",
        date_str=datetime.now().strftime('%d-%b-%Y'),
        teacher_name=teacher_name,
        session_title="Admin Test Alert",
        force_test=True
    )
