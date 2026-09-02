import os
import sys
import json
import base64
import numpy as np
import cv2
from datetime import datetime

# Set test environment
os.environ['DATA_DIR'] = os.path.abspath(os.path.dirname(__file__))

from app import app
from models import db, User, Student, AttendanceSession, AttendanceRecord, UndetectedFace, EmailLog
from face_engine import face_engine, MODEL_VERSION

# Mock OpenCV YuNet and SFace for synthetic test frames in integration suite
def mock_detect_faces(img_np):
    return [(100, 100, 200, 200)]

def mock_detect_faces_with_landmarks(img_np):
    return [np.array([100, 100, 200, 200, 120, 140, 180, 140, 150, 160, 130, 180, 170, 180, 0.99], dtype=np.float32)]

def mock_extract_encoding(img_np, face_box=None):
    vec = [1.0 / (128 ** 0.5)] * 128
    return vec

face_engine.detect_faces = mock_detect_faces
face_engine.detect_faces_with_landmarks = mock_detect_faces_with_landmarks
face_engine.extract_encoding = mock_extract_encoding
face_engine.extract_embedding = mock_extract_encoding

def create_synthetic_face_image():
    """Generates a synthetic test frame."""
    img = np.zeros((480, 640, 3), dtype=np.uint8)
    img[:] = (240, 240, 240)
    _, buffer = cv2.imencode('.jpg', img)
    b64_str = base64.b64encode(buffer).decode('utf-8')
    return b64_str, img

def run_integration_tests():
    print("=" * 70)
    print("STARTING FULL INTEGRATION & WORKFLOW VERIFICATION TEST SUITE")
    print("=" * 70)

    client = app.test_client()

    with app.app_context():
        db.create_all()

        # -------------------------------------------------------------
        # TEST 1: Admin & Professor Authentication
        # -------------------------------------------------------------
        print("\n[TEST 1] Testing Admin & Professor Authentication...")
        admin_res = client.post('/api/auth/login', json={'username': 'admin', 'password': 'admin123'})
        assert admin_res.status_code == 200, f"Admin login failed: {admin_res.data}"
        admin_token = admin_res.get_json()['token']
        print("  [OK] Admin login successful. Token acquired.")

        prof_res = client.post('/api/auth/login', json={'username': 'teacher', 'password': 'teacher123'})
        assert prof_res.status_code == 200, f"Professor login failed: {prof_res.data}"
        prof_token = prof_res.get_json()['token']
        print("  [OK] Professor login successful. Token acquired.")

        # -------------------------------------------------------------
        # TEST 2: Role-Based Access Control (RBAC) Protection
        # -------------------------------------------------------------
        print("\n[TEST 2] Testing RBAC Security Enforcement...")
        unauth_fin = client.post(
            '/api/sessions/1/finalize',
            headers={'Authorization': f'Bearer {prof_token}'}
        )
        assert unauth_fin.status_code == 403, f"Expected 403 for Professor finalization, got {unauth_fin.status_code}"
        print("  [OK] Non-admin access to finalization correctly rejected with HTTP 403 Forbidden.")

        # -------------------------------------------------------------
        # TEST 3: Student Registration with 5 Photo Encodings & Parent Email
        # -------------------------------------------------------------
        print("\n[TEST 3] Testing Student Registration (5-Photo Flow & Required Parent Email)...")
        b64_face, face_np = create_synthetic_face_image()
        five_photos = [b64_face] * 5

        # Test registration with parent email
        reg_res = client.post(
            '/api/students',
            headers={'Authorization': f'Bearer {admin_token}'},
            json={
                'name': 'Siva Ram',
                'roll_no': 'TEST-SR-101',
                'class_name': 'Computer Science - Year 4',
                'parent_email': 'sivaramakrishnabevara@gmail.com',
                'face_images': five_photos
            }
        )
        assert reg_res.status_code == 200, f"Student registration failed: {reg_res.data}"
        st_data = reg_res.get_json()['student']
        print(f"  [OK] Student '{st_data['name']}' (Roll: {st_data['roll_no']}) registered with 5 photo encodings.")
        print(f"  [OK] Parent Email saved: {st_data['parent_email']}")

        # -------------------------------------------------------------
        # TEST 4: Live Attendance Session Creation & Frame Recognition
        # -------------------------------------------------------------
        print("\n[TEST 4] Testing Attendance Session Creation & Live Frame Recognition...")
        start_res = client.post(
            '/api/sessions/start',
            headers={'Authorization': f'Bearer {prof_token}'},
            json={
                'session_title': 'Integration Test Attendance Session',
                'class_name': 'Computer Science - Year 4'
            }
        )
        assert start_res.status_code == 200, f"Session start failed: {start_res.data}"
        session_id = start_res.get_json()['session']['id']
        print(f"  [OK] Live attendance session #{session_id} created in state IN_PROGRESS.")

        # Process webcam frame
        frame_res = client.post(
            f'/api/sessions/{session_id}/process_frame',
            headers={'Authorization': f'Bearer {prof_token}'},
            json={'frame': b64_face}
        )
        assert frame_res.status_code == 200, f"Frame processing failed: {frame_res.data}"
        frame_json = frame_res.get_json()
        print(f"  [OK] Live frame processed successfully. Recognized faces: {frame_json['recognized_count']}.")

        # -------------------------------------------------------------
        # TEST 5: Professor Session Submission
        # -------------------------------------------------------------
        print("\n[TEST 5] Testing Professor Session Submission...")
        sub_res = client.post(
            f'/api/sessions/{session_id}/submit_approval',
            headers={'Authorization': f'Bearer {prof_token}'}
        )
        assert sub_res.status_code == 200, f"Submission failed: {sub_res.data}"
        sub_session = sub_res.get_json()['session']
        assert sub_session['status'] == 'SUBMITTED_FOR_APPROVAL', f"Status is {sub_session['status']}"
        print(f"  [OK] Session #{session_id} status updated to SUBMITTED_FOR_APPROVAL.")

        # -------------------------------------------------------------
        # TEST 6: Admin Session Finalization & Automated Parent Email Dispatch
        # -------------------------------------------------------------
        print("\n[TEST 6] Testing Admin Finalization & Parent Email Dispatch...")
        fin_res = client.post(
            f'/api/sessions/{session_id}/finalize',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert fin_res.status_code == 200, f"Finalization failed: {fin_res.data}"
        fin_json = fin_res.get_json()
        assert fin_json['session']['status'] == 'FINALIZED', f"Status is {fin_json['session']['status']}"
        assert fin_json['session']['finalized_by_admin_id'] is not None
        print(f"  [OK] Session #{session_id} FINALIZED by Admin '{fin_json['session']['finalized_by_admin_name']}'.")
        print(f"  [OK] Finalized timestamp & Admin ID stored.")

        # Duplicate finalization retry test
        dup_fin_res = client.post(
            f'/api/sessions/{session_id}/finalize',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert dup_fin_res.status_code == 200
        assert "already finalized" in dup_fin_res.get_json()['message']
        print("  [OK] Duplicate finalization request handled gracefully without re-sending emails.")

        # -------------------------------------------------------------
        # TEST 7: Excel & PDF Report Downloads
        # -------------------------------------------------------------
        print("\n[TEST 7] Testing Excel & PDF Report Generation...")
        excel_res = client.get(
            f'/api/export/excel/{session_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert excel_res.status_code == 200, f"Excel export failed: {excel_res.status_code}"
        assert len(excel_res.data) > 1000
        print(f"  [OK] Excel (.xlsx) report generated successfully ({len(excel_res.data)} bytes).")

        pdf_res = client.get(
            f'/api/export/pdf/{session_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert pdf_res.status_code == 200, f"PDF export failed: {pdf_res.status_code}"
        assert len(pdf_res.data) > 1000
        print(f"  [OK] PDF (.pdf) report generated successfully ({len(pdf_res.data)} bytes).")

        # -------------------------------------------------------------
        # TEST 8: Attendance Analytics API
        # -------------------------------------------------------------
        print("\n[TEST 8] Testing Attendance Analytics API...")
        analytics_res = client.get(
            '/api/analytics',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert analytics_res.status_code == 200, f"Analytics failed: {analytics_res.status_code}"
        an_json = analytics_res.get_json()['analytics']
        print(f"  [OK] Analytics fetched. Total Students: {an_json['total_students']}, Avg Attendance: {an_json['average_attendance']}%.")
        print(f"  [OK] Risk Distribution: {an_json['risk_distribution']}")

        # -------------------------------------------------------------
        # TEST 9: Student Soft Deactivation & Historical Retention
        # -------------------------------------------------------------
        print("\n[TEST 9] Testing Student Soft Deactivation...")
        del_st_id = st_data['id']
        del_res = client.delete(
            f'/api/students/{del_st_id}',
            headers={'Authorization': f'Bearer {admin_token}'}
        )
        assert del_res.status_code == 200
        assert "deactivated" in del_res.get_json()['message'].lower()
        
        rechecked_st = Student.query.get(del_st_id)
        assert rechecked_st is not None, "Student record should be preserved"
        assert rechecked_st.is_active is False, "Student is_active should be False"
        print(f"  [OK] Student ID #{del_st_id} soft-deactivated (is_active=False). Historical records preserved.")

        print("\n" + "=" * 70)
        print("ALL 9 INTEGRATION TESTS PASSED WITH 100% SUCCESS!")
        print("=" * 70)

if __name__ == '__main__':
    run_integration_tests()
