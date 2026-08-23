import os
from werkzeug.security import generate_password_hash
from models import db, User, Student
from config import Config

def init_db(app):
    """
    Initializes database tables, creates required dataset directories,
    and seeds initial Admin and Teacher accounts if not present.
    """
    # Ensure directories exist
    os.makedirs(Config.STUDENT_DATASET_DIR, exist_ok=True)
    os.makedirs(Config.UNDETECTED_FACES_DIR, exist_ok=True)
    os.makedirs(Config.SESSION_SNAPSHOTS_DIR, exist_ok=True)
    os.makedirs(Config.EXPORT_DIR, exist_ok=True)

    with app.app_context():
        # Set SQLite WAL mode and busy timeout for concurrent safety
        try:
            with db.engine.connect() as conn:
                conn.exec_driver_sql("PRAGMA journal_mode=WAL;")
                conn.exec_driver_sql("PRAGMA busy_timeout=30000;")
        except Exception:
            pass

        db.create_all()

        # Seed default Admin
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                password_hash=generate_password_hash('admin123'),
                role='ADMIN',
                full_name='System Administrator',
                email='admin@school.edu'
            )
            db.session.add(admin)

        # Seed default Teacher
        teacher = User.query.filter_by(username='teacher').first()
        if not teacher:
            teacher = User(
                username='teacher',
                password_hash=generate_password_hash('teacher123'),
                role='TEACHER',
                full_name='Prof. Sarah Jenkins',
                email='s.jenkins@school.edu'
            )
            db.session.add(teacher)

        # Seed sample students for quick testing if empty
        if Student.query.count() == 0:
            s1 = Student(
                student_code='STU001',
                name='Alex Johnson',
                roll_no='CS-101',
                class_name='Computer Science - Year 4',
                parent_email='parent.alex@gmail.com',
                parent_phone='+1987654321'
            )
            s2 = Student(
                student_code='STU002',
                name='Emily Carter',
                roll_no='CS-102',
                class_name='Computer Science - Year 4',
                parent_email='parent.emily@gmail.com',
                parent_phone='+1987654322'
            )
            s3 = Student(
                student_code='STU003',
                name='Michael Chang',
                roll_no='CS-103',
                class_name='Computer Science - Year 4',
                parent_email='parent.michael@gmail.com',
                parent_phone='+1987654323'
            )
            db.session.add_all([s1, s2, s3])

        db.session.commit()
        print("Database initialized and default seed data loaded successfully.")
