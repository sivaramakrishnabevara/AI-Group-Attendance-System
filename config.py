import os

BASE_DIR = os.path.abspath(os.path.dirname(__file__))

class Config:
    BASE_DIR = BASE_DIR
    SECRET_KEY = os.environ.get('SECRET_KEY', 'smart_group_attendance_secret_key_2026_xyz')
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(BASE_DIR, 'attendance_system.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        'connect_args': {'timeout': 30},
        'pool_pre_ping': True
    }
    
    # Dataset Folders
    STUDENT_DATASET_DIR = os.path.join(BASE_DIR, 'dataset', 'students')
    UNDETECTED_FACES_DIR = os.path.join(BASE_DIR, 'dataset', 'undetected_faces')
    SESSION_SNAPSHOTS_DIR = os.path.join(BASE_DIR, 'dataset', 'session_snapshots')
    EXPORT_DIR = os.path.join(BASE_DIR, 'dataset', 'exports')
    
    # SMTP Email Configuration for Parent Alerts
    SMTP_SERVER = os.environ.get('SMTP_SERVER', 'smtp.gmail.com')
    SMTP_PORT = int(os.environ.get('SMTP_PORT', 587))
    SMTP_EMAIL = os.environ.get('SMTP_EMAIL', 'attendance.system.notify@gmail.com')
    SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '') # Set real App Password if live email is used
    ENABLE_REAL_EMAIL = False # If False, emails are logged to console & DB for testing
    
    # Face Recognition Threshold (Cosine Distance / Similarity)
    MATCH_THRESHOLD = 0.65
