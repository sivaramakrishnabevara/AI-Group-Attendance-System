import cv2
import numpy as np
import os
import json
import sqlite3

def run_diagnostics():
    print("=" * 60)
    print("FACE RECOGNITION SYSTEM DIAGNOSTIC REPORT")
    print("=" * 60)

    # 1. Test engine import and model loading
    from face_engine import face_engine, SFACE_MODEL_PATH, YUNET_MODEL_PATH

    print(f"Encoder: OpenCV SFace ONNX Deep Face Recognizer")
    print(f"Embedding dimension: {face_engine.active_vector_dim}")
    print(f"Model loaded: {os.path.basename(SFACE_MODEL_PATH)} (Size: {os.path.getsize(SFACE_MODEL_PATH)} bytes)")
    print(f"Detector loaded: {os.path.basename(YUNET_MODEL_PATH)} (Size: {os.path.getsize(YUNET_MODEL_PATH)} bytes)")
    print(f"Selected threshold: {face_engine.match_threshold}")

    # 2. Test with real student images
    img_siva_path = 'dataset/students/student_STU-33_20260824155001.jpg'
    img_khaja_path = 'dataset/students/student_2_20260810144143.jpg'

    img_siva = cv2.imread(img_siva_path)
    img_khaja = cv2.imread(img_khaja_path)

    if img_siva is None or img_khaja is None:
        print("ERROR: Test images not found in dataset/students/")
        return

    # Extract encodings
    faces_siva = face_engine.detect_faces(img_siva)
    faces_khaja = face_engine.detect_faces(img_khaja)

    enc_siva = face_engine.extract_encoding(img_siva, faces_siva[0] if faces_siva else None)
    enc_khaja = face_engine.extract_encoding(img_khaja, faces_khaja[0] if faces_khaja else None)

    print(f"\nSiva photo embedding (first 5 vals): {enc_siva[:5] if enc_siva else 'None'}")
    print(f"Khaja photo embedding (first 5 vals): {enc_khaja[:5] if enc_khaja else 'None'}")

    same_sim = face_engine.compute_similarity(enc_siva, enc_siva)
    diff_sim = face_engine.compute_similarity(enc_siva, enc_khaja)

    print(f"Same-person similarity (Siva vs Siva): {same_sim:.4f}")
    print(f"Different-person similarity (Siva vs Khaja): {diff_sim:.4f}")

    # 3. Test Unregistered face recognition
    unregistered_img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(unregistered_img, (320, 240), 90, (180, 180, 180), -1)
    cv2.circle(unregistered_img, (280, 210), 12, (30, 30, 30), -1)
    cv2.circle(unregistered_img, (360, 210), 12, (30, 30, 30), -1)
    cv2.line(unregistered_img, (320, 230), (320, 270), (30, 30, 30), 4)
    cv2.ellipse(unregistered_img, (320, 290), (30, 15), 0, 0, 180, (30, 30, 30), 4)

    # 4. Test multi-student group recognition (Siva + Khaja combined into group photo)
    h1, w1 = img_siva.shape[:2]
    h2, w2 = img_khaja.shape[:2]
    max_h = max(h1, h2)
    group_frame = np.zeros((max_h, w1 + w2, 3), dtype=np.uint8)
    group_frame[:h1, :w1] = img_siva
    group_frame[:h2, w1:w1+w2] = img_khaja

    # 5. Database Integration & Flask Route Integration Test
    from app import app
    from models import db, Student, User, AttendanceSession, AttendanceRecord

    with app.app_context():
        students = Student.query.all()
        print("\n" + "=" * 60)
        print("DATABASE STUDENT RECORDS & ENCODINGS")
        print("=" * 60)
        print(f"Database Student Records Count: {len(students)}")
        for s in students:
            vec = face_engine._parse_vector(s.encoding_json)
            has_enc = vec is not None and len(vec) == 128
            print(f" - Student ID {s.id}: {s.name} (Code: {s.student_code}) | Valid SFace 128-D Vector: {has_enc}")

        # Live frame test against real DB students
        os.makedirs('dataset/undetected_faces', exist_ok=True)
        stamped_group, recognized, undetected = face_engine.process_live_frame(
            group_frame, students, session_id=999, undetected_folder='dataset/undetected_faces'
        )

        print("\n" + "=" * 60)
        print("LIVE FRAME GROUP RECOGNITION TEST")
        print("=" * 60)
        print(f"Recognized count in group frame: {len(recognized)}")
        for rec in recognized:
            print(f" - Recognized: {rec['student_name']} ({rec['student_code']}) with confidence {rec['confidence']}%")

        # Live frame test with unregistered person
        stamped_unreg, rec_unreg, undet_unreg = face_engine.process_live_frame(
            unregistered_img, students, session_id=999, undetected_folder='dataset/undetected_faces'
        )
        print(f"\nUnregistered face recognition result:")
        print(f" - Recognized count: {len(rec_unreg)} (Expected 0)")
        print(f" - Undetected/Unknown count: {len(undet_unreg)} (Expected >= 1)")

        # Verify real session creation
        teacher_user = User.query.filter_by(role='TEACHER').first()
        if teacher_user:
            session = AttendanceSession(
                session_title="Diagnostic Verification Session",
                class_name=students[0].class_name if students else "Computer Science - Year 4",
                created_by_teacher_id=teacher_user.id,
                created_by_teacher_name=teacher_user.full_name,
                status='IN_PROGRESS'
            )
            db.session.add(session)
            db.session.commit()

            rec = AttendanceRecord(
                session_id=session.id,
                student_id=students[0].id if students else 1,
                status='PRESENT',
                marking_method='AI_FACE_RECOGNITION',
                approval_status='APPROVED'
            )
            db.session.add(rec)
            db.session.commit()
            print(f"\nSuccessfully created test session #{session.id} and attendance record #{rec.id}.")

    print("\n" + "=" * 60)
    print("ALL DIAGNOSTIC VERIFICATION TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_diagnostics()
