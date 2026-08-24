import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
# Support persistent storage directory via DATA_DIR environment variable (e.g., Render Persistent Disk mounted at /data)
DATA_DIR = os.environ.get('DATA_DIR', BASE_DIR)

class Config:
    BASE_DIR = BASE_DIR
    DATA_DIR = DATA_DIR
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart_group_attendance_secret_key_2026_xyz')
    # Database Configuration: PostgreSQL on Render (via DATABASE_URL), SQLite fallback for local dev
    db_url = os.environ.get('DATABASE_URL')
    if db_url:
        if db_url.startswith('postgres://'):
            db_url = db_url.replace('postgres://', 'postgresql://', 1)
        SQLALCHEMY_DATABASE_URI = db_url
        SQLALCHEMY_ENGINE_OPTIONS = {
            'pool_pre_ping': True
        }
    else:
        SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(DATA_DIR, 'attendance_system.db')
        SQLALCHEMY_ENGINE_OPTIONS = {
            'connect_args': {'timeout': 30},
            'pool_pre_ping': True
        }
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Dataset Folders
    STUDENT_DATASET_DIR = os.path.join(DATA_DIR, 'dataset', 'students')
    UNKNOWN_FACES_DIR = os.path.join(DATA_DIR, 'dataset', 'unknown_faces')
    UNDETECTED_FACES_DIR = os.path.join(DATA_DIR, 'dataset', 'unknown_faces')
    SESSION_SNAPSHOTS_DIR = os.path.join(DATA_DIR, 'dataset', 'session_snapshots')
    EXPORT_DIR = os.path.join(DATA_DIR, 'dataset', 'exports')
    
    # Gmail SMTP Configuration for Parent Absence Alerts
    ENABLE_EMAIL_ALERTS = os.environ.get('ENABLE_EMAIL_ALERTS', 'True').lower() in ('true', '1', 't')
    GMAIL_EMAIL = os.environ.get('GMAIL_EMAIL', '')
    GMAIL_APP_PASSWORD = os.environ.get('GMAIL_APP_PASSWORD', '')
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))

    # Provider-Independent SMS Configuration for Parent Absence Alerts (Legacy / Optional)
    SMS_MODE = os.environ.get('SMS_MODE', 'SIMULATION') # 'SIMULATION' or 'REAL_SMS'
    SMS_ENABLED = os.environ.get('SMS_ENABLED', 'True').lower() in ('true', '1', 't')
    SMS_PROVIDER = os.environ.get('SMS_PROVIDER', 'GENERIC_HTTP')
    SMS_API_KEY = os.environ.get('SMS_API_KEY', '')
    SMS_API_SECRET = os.environ.get('SMS_API_SECRET', '')
    SMS_SENDER_ID = os.environ.get('SMS_SENDER_ID', 'ATTNDS')
    SMS_HTTP_URL = os.environ.get('SMS_HTTP_URL', '')
    SMS_ROUTE = os.environ.get('SMS_ROUTE', 'q')
    SMS_DLT_TE_ID = os.environ.get('SMS_DLT_TE_ID', '')
    
    # Face Recognition Threshold (Cosine Distance / Similarity)
    MATCH_THRESHOLD = 0.40

