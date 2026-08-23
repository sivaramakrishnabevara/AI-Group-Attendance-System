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

        # Migrate legacy student face encodings to SFACE_ONNX_V1 format
        try:
            from face_engine import face_engine, MODEL_VERSION
            import json
            import cv2

            all_students = Student.query.all()
            migrated_count = 0
            for st in all_students:
                needs_migration = False
                if not st.encoding_json:
                    needs_migration = True
                else:
                    try:
                        enc_data = json.loads(st.encoding_json)
                        if isinstance(enc_data, dict):
                            if enc_data.get('version') != MODEL_VERSION:
                                needs_migration = True
                        else:
                            needs_migration = True
                    except Exception:
                        needs_migration = True

                if needs_migration and st.face_image_path:
                    full_p = os.path.join(Config.DATA_DIR, st.face_image_path)
                    if os.path.exists(full_p):
                        st_img = cv2.imread(full_p)
                        if st_img is not None:
                            faces = face_engine.detect_faces(st_img)
                            f_box = faces[0] if len(faces) > 0 else None
                            enc_vec = face_engine.extract_encoding(st_img, f_box)
                            if enc_vec:
                                st.encoding_json = json.dumps({
                                    'version': MODEL_VERSION,
                                    'vector': enc_vec
                                })
                                migrated_count += 1

            if migrated_count > 0:
                db.session.commit()
                print(f"Migrated {migrated_count} student face encodings to {MODEL_VERSION} format.")
        except Exception as e:
            print(f"Encoding migration notice: {e}")

        print("Database initialized and default seed data loaded successfully.")

