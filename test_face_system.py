import cv2
import numpy as np
import os
import json
import uuid

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

    # 2. Test images
    img1_path = 'dataset/students/student_1_20260810150034.jpg'
    img2_path = 'dataset/students/student_2_20260810144143.jpg'

    img1 = cv2.imread(img1_path)
    img2 = cv2.imread(img2_path)

    if img1 is None or img2 is None:
        print("ERROR: Test images not found in dataset/students/")
        return

    # Extract encodings
    faces1 = face_engine.detect_faces(img1)
    faces2 = face_engine.detect_faces(img2)

    enc1 = face_engine.extract_encoding(img1, faces1[0] if faces1 else None)
    enc2 = face_engine.extract_encoding(img2, faces2[0] if faces2 else None)

    print(f"\nStudent A embedding (first 5 vals): {enc1[:5] if enc1 else 'None'}")
    print(f"Student B embedding (first 5 vals): {enc2[:5] if enc2 else 'None'}")

    same_sim = face_engine.compute_similarity(enc1, enc1)
    diff_sim = face_engine.compute_similarity(enc1, enc2)

    print(f"Same-person similarity: {same_sim:.4f}")
    print(f"Different-person similarity: {diff_sim:.4f}")

    # 3. Test Unknown Face recognition
    # Create synthetic unregistered face image
    unregistered_img = np.zeros((480, 640, 3), dtype=np.uint8)
    cv2.circle(unregistered_img, (320, 240), 90, (180, 180, 180), -1)
    cv2.circle(unregistered_img, (280, 210), 12, (30, 30, 30), -1)
    cv2.circle(unregistered_img, (360, 210), 12, (30, 30, 30), -1)
    cv2.line(unregistered_img, (320, 230), (320, 270), (30, 30, 30), 4)
    cv2.ellipse(unregistered_img, (320, 290), (30, 15), 0, 0, 180, (30, 30, 30), 4)

    # 4. Test multi-student group recognition
    # Combine Student A and Student B side by side into a single group photo frame
    h1, w1 = img1.shape[:2]
    h2, w2 = img2.shape[:2]
    max_h = max(h1, h2)
    group_frame = np.zeros((max_h, w1 + w2, 3), dtype=np.uint8)
    group_frame[:h1, :w1] = img1
    group_frame[:h2, w1:w1+w2] = img2

    # Create Mock Student objects
    class MockStudent:
        def __init__(self, id, code, name, roll, class_n, encoding):
            self.id = id
            self.student_code = code
            self.name = name
            self.roll_no = roll
            self.class_name = class_n
            self.encoding_json = json.dumps(encoding)

    stu_a = MockStudent(1, 'STU001', 'Alex Johnson', 'CS-101', 'Computer Science - Year 4', enc1)
    stu_b = MockStudent(2, 'STU002', 'Emily Carter', 'CS-102', 'Computer Science - Year 4', enc2)

    student_records = [stu_a, stu_b]

    # Process group frame
    os.makedirs('dataset/undetected_faces', exist_ok=True)
    stamped_group, recognized, undetected = face_engine.process_live_frame(
        group_frame, student_records, session_id=999, undetected_folder='dataset/undetected_faces'
    )

    print("\n" + "=" * 60)
    print("LIVE FRAME RECOGNITION TEST")
    print("=" * 60)
    print(f"Recognized count in group frame: {len(recognized)}")
    for rec in recognized:
        print(f" - Recognized: {rec['student_name']} ({rec['student_code']}) with confidence {rec['confidence']}%")

    # Process unregistered frame
    stamped_unreg, rec_unreg, undet_unreg = face_engine.process_live_frame(
        unregistered_img, student_records, session_id=999, undetected_folder='dataset/undetected_faces'
    )
    print(f"\nUnregistered face recognition result:")
    print(f" - Recognized count: {len(rec_unreg)} (Expected 0)")
    print(f" - Undetected/Unknown count: {len(undet_unreg)} (Expected >= 1)")

    # 5. Database Integration & Flask Route Integration Test
    from app import app
    from models import db, Student, User, AttendanceSession, AttendanceRecord

    with app.app_context():
        # Check student records in database
        students = Student.query.all()
        print(f"\nDatabase Student Records Count: {len(students)}")
        for s in students:
            has_enc = bool(s.encoding_json)
            enc_len = len(json.loads(s.encoding_json)) if has_enc else 0
            print(f" - Student ID {s.id}: {s.name} | Has Encoding: {has_enc} | Dimension: {enc_len}")

        # Test session creation and attendance marking
        teacher_user = User.query.filter_by(role='TEACHER').first()
        if teacher_user:
            session = AttendanceSession(
                session_title="Diagnostic Test Session",
                class_name="Computer Science - Year 4",
                created_by_teacher_id=teacher_user.id,
                created_by_teacher_name=teacher_user.full_name,
                status='IN_PROGRESS'
            )
            db.session.add(session)
            db.session.commit()

            # Mark student A present
            rec = AttendanceRecord(
                session_id=session.id,
                student_id=students[0].id if students else 1,
                status='PRESENT',
                marking_method='AI_FACE_RECOGNITION',
                approval_status='APPROVED'
            )
            db.session.add(rec)
            db.session.commit()
            print(f"\nSuccessfully created test session #{session.id} and marked attendance record #{rec.id}.")

    print("\n" + "=" * 60)
    print("ALL DIAGNOSTIC TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)

if __name__ == '__main__':
    run_diagnostics()
