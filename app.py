import os
import base64
import json
import jwt
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, send_file
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
import cv2
import numpy as np

from config import Config
from models import db, User, Student, AttendanceSession, AttendanceRecord, UndetectedFace, SystemSetting
from database import init_db
from face_engine import face_engine
from email_service import send_parent_absent_email
from exporter import export_attendance_to_excel, export_attendance_to_pdf

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(Config)

allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
CORS(app, origins=allowed_origins if allowed_origins != ['*'] else '*', supports_credentials=True)

db.init_app(app)

# Initialize DB and directories
init_db(app)

# -------------------------------------------------------------------
# Auth Decorators
# -------------------------------------------------------------------
def token_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        token = None
        if 'Authorization' in request.headers:
            auth_header = request.headers['Authorization']
            if auth_header.startswith('Bearer '):
                token = auth_header.split(' ')[1]
        
        if not token:
            return jsonify({'success': False, 'message': 'Authentication token is missing'}), 401
        
        try:
            data = jwt.decode(token, app.config['SECRET_KEY'], algorithms=['HS256'])
            current_user = User.query.get(data['user_id'])
            if not current_user:
                return jsonify({'success': False, 'message': 'Invalid token user'}), 401
        except Exception as e:
            return jsonify({'success': False, 'message': 'Token is invalid or expired'}), 401

        return f(current_user, *args, **kwargs)
    return decorated

def admin_only(f):
    @wraps(f)
    def decorated(current_user, *args, **kwargs):
        if current_user.role != 'ADMIN':
            return jsonify({'success': False, 'message': 'Admin privilege required'}), 403
        return f(current_user, *args, **kwargs)
    return decorated

# Helper: Convert Base64 Data URL to OpenCV BGR Image
def base64_to_cv2(b64_string):
    try:
        if ',' in b64_string:
            b64_string = b64_string.split(',')[1]
        img_data = base64.b64decode(b64_string)
        np_arr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(np_arr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        return None

# -------------------------------------------------------------------
# Static & Page Serving Routes
# -------------------------------------------------------------------
@app.route('/')
def index():
    return send_file('templates/index.html')

@app.route('/dataset/<path:filename>')
def serve_dataset(filename):
    return send_from_directory(os.path.join(Config.DATA_DIR, 'dataset'), filename)

# -------------------------------------------------------------------
# Authentication Routes
# -------------------------------------------------------------------
@app.route('/api/auth/login', methods=['POST'])
def login():
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({'success': False, 'message': 'Username and password are required'}), 400

    user = User.query.filter_by(username=username).first()
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'success': False, 'message': 'Invalid credentials'}), 401

    token = jwt.encode({
        'user_id': user.id,
        'role': user.role,
        'exp': datetime.utcnow() + timedelta(hours=12)
    }, app.config['SECRET_KEY'], algorithm='HS256')

    return jsonify({
        'success': True,
        'token': token,
        'user': user.to_dict()
    })

@app.route('/api/auth/me', methods=['GET'])
@token_required
def get_me(current_user):
    return jsonify({
        'success': True,
        'user': current_user.to_dict()
    })

# -------------------------------------------------------------------
# Admin Management Routes (Teachers & Students)
# -------------------------------------------------------------------
@app.route('/api/teachers', methods=['GET'])
@token_required
@admin_only
def get_teachers(current_user):
    teachers = User.query.filter_by(role='TEACHER').all()
    return jsonify({
        'success': True,
        'teachers': [t.to_dict() for t in teachers]
    })

@app.route('/api/teachers', methods=['POST'])
@token_required
@admin_only
def add_teacher(current_user):
    data = request.get_json() or {}
    username = data.get('username')
    password = data.get('password')
    full_name = data.get('full_name')
    email = data.get('email')

    if not all([username, password, full_name, email]):
        return jsonify({'success': False, 'message': 'All teacher fields are required'}), 400

    if User.query.filter_by(username=username).first():
        return jsonify({'success': False, 'message': 'Username already exists'}), 400

    teacher = User(
        username=username,
        password_hash=generate_password_hash(password),
        role='TEACHER',
        full_name=full_name,
        email=email
    )
    db.session.add(teacher)
    db.session.commit()

    return jsonify({'success': True, 'message': 'Teacher added successfully', 'teacher': teacher.to_dict()})

@app.route('/api/teachers/<int:teacher_id>', methods=['DELETE'])
@token_required
@admin_only
def delete_teacher(current_user, teacher_id):
    teacher = User.query.filter_by(id=teacher_id, role='TEACHER').first()
    if not teacher:
        return jsonify({'success': False, 'message': 'Teacher not found'}), 404

    db.session.delete(teacher)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Teacher deleted successfully'})

@app.route('/api/teachers/<int:teacher_id>', methods=['PUT'])
@token_required
@admin_only
def update_teacher(current_user, teacher_id):
    """Admin can edit teacher details: full_name, username, email, password (optional)."""
    teacher = User.query.filter_by(id=teacher_id, role='TEACHER').first()
    if not teacher:
        return jsonify({'success': False, 'message': 'Teacher not found'}), 404

    data = request.get_json() or {}
    full_name = data.get('full_name', '').strip()
    username = data.get('username', '').strip()
    email = data.get('email', '').strip()
    password = data.get('password', '').strip()

    if not all([full_name, username, email]):
        return jsonify({'success': False, 'message': 'Full name, username, and email are required'}), 400

    # Check username uniqueness (exclude current teacher)
    existing = User.query.filter(User.username == username, User.id != teacher_id).first()
    if existing:
        return jsonify({'success': False, 'message': 'Username already taken by another user'}), 400

    teacher.full_name = full_name
    teacher.username = username
    teacher.email = email
    if password:
        teacher.password_hash = generate_password_hash(password)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Teacher updated successfully', 'teacher': teacher.to_dict()})

# -------------------------------------------------------------------
# Student Management Routes (Teacher + Admin)
# -------------------------------------------------------------------
@app.route('/api/students', methods=['GET'])
@token_required
def get_students(current_user):
    class_filter = request.args.get('class_name')
    query = Student.query
    if class_filter:
        query = query.filter_by(class_name=class_filter)
    students = query.all()
    return jsonify({
        'success': True,
        'students': [s.to_dict() for s in students]
    })

@app.route('/api/students', methods=['POST'])
@token_required
def add_student(current_user):
    """
    Creates a student and extracts face encoding from live captured photo frame.
    Req 5: If add student after filled details, capture face to store student data in separate folder.
    """
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    roll_no = data.get('roll_no', '').strip()
    class_name = data.get('class_name', '').strip()
    parent_email = data.get('parent_email', '').strip()
    parent_phone = data.get('parent_phone', '')
    student_code = data.get('student_code', '').strip()
    face_image_b64 = data.get('face_image')

    if not all([name, roll_no, class_name, parent_email]):
        return jsonify({'success': False, 'message': 'Full Name, Roll Number, Class Name, and Parent Email are required'}), 400

    if not student_code:
        student_code = f"STU-{roll_no}"
        counter = 1
        base_code = student_code
        while Student.query.filter_by(student_code=student_code).first():
            student_code = f"{base_code}-{counter}"
            counter += 1
    elif Student.query.filter_by(student_code=student_code).first():
        return jsonify({'success': False, 'message': 'Student Code already registered'}), 400

    encoding_json = None
    face_rel_path = None

    if face_image_b64:
        img_np = base64_to_cv2(face_image_b64)
        if img_np is not None:
            faces = face_engine.detect_faces(img_np)
            if len(faces) > 0:
                x, y, w, h = faces[0]
                encoding = face_engine.extract_encoding(img_np, (x, y, w, h))
                if encoding:
                    encoding_json = json.dumps(encoding)

                # Save face image crop in dataset/students/
                filename = f"student_{student_code}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
                save_path = os.path.join(Config.STUDENT_DATASET_DIR, filename)
                cv2.imwrite(save_path, img_np)
                face_rel_path = f"dataset/students/{filename}"

    student = Student(
        student_code=student_code,
        name=name,
        roll_no=roll_no,
        class_name=class_name,
        parent_email=parent_email,
        parent_phone=parent_phone,
        face_image_path=face_rel_path,
        encoding_json=encoding_json
    )
    db.session.add(student)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Student registered successfully' + (' with face encoding' if encoding_json else ' (No face detected in photo)'),
        'student': student.to_dict()
    })

@app.route('/api/students/<int:student_id>', methods=['DELETE'])
@token_required
@admin_only
def delete_student(current_user, student_id):
    """
    Req 3: Admin can delete student.
    """
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    # Remove face image file if exists
    if student.face_image_path:
        full_p = os.path.join(Config.DATA_DIR, student.face_image_path)
        if os.path.exists(full_p):
            try:
                os.remove(full_p)
            except Exception:
                pass

    # Cleanly delete associated attendance records and reset undetected face claims
    AttendanceRecord.query.filter_by(student_id=student_id).delete()
    UndetectedFace.query.filter_by(claimed_student_id=student_id).update({
        'claimed_student_id': None,
        'status': 'UNCLAIMED'
    })

    db.session.delete(student)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Student deleted successfully'})

@app.route('/api/students/<int:student_id>', methods=['PUT'])
@token_required
@admin_only
def update_student(current_user, student_id):
    """Admin can edit student details: name, roll_no, class_name, parent_email, student_code."""
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    data = request.get_json() or {}
    student_code = data.get('student_code', '').strip()
    name = data.get('name', '').strip()
    roll_no = data.get('roll_no', '').strip()
    class_name = data.get('class_name', '').strip()
    parent_email = data.get('parent_email', '').strip()

    if not all([name, roll_no, class_name, parent_email]):
        return jsonify({'success': False, 'message': 'Name, Roll Number, Class Name, and Parent Email are required'}), 400

    if student_code:
        existing = Student.query.filter(Student.student_code == student_code, Student.id != student_id).first()
        if existing:
            return jsonify({'success': False, 'message': 'Student code already used by another student'}), 400
        student.student_code = student_code

    student.name = name
    student.roll_no = roll_no
    student.class_name = class_name
    student.parent_email = parent_email

    db.session.commit()
    return jsonify({'success': True, 'message': 'Student updated successfully', 'student': student.to_dict()})

@app.route('/api/students/<int:student_id>/face', methods=['POST'])
@token_required
def update_student_face(current_user, student_id):
    """
    Captures photo from webcam and updates student's face encoding & dataset image.
    Accessible to Admin and Teacher.
    """
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    data = request.get_json() or {}
    face_image_b64 = data.get('face_image')
    if not face_image_b64:
        return jsonify({'success': False, 'message': 'No face image provided'}), 400

    img_np = base64_to_cv2(face_image_b64)
    if img_np is None:
        return jsonify({'success': False, 'message': 'Invalid image format'}), 400

    faces = face_engine.detect_faces(img_np)
    encoding_json = None
    if len(faces) > 0:
        x, y, w, h = faces[0]
        encoding = face_engine.extract_encoding(img_np, (x, y, w, h))
        if encoding:
            encoding_json = json.dumps(encoding)

    # Remove old face image if exists
    if student.face_image_path:
        old_path = os.path.join(Config.DATA_DIR, student.face_image_path)
        if os.path.exists(old_path):
            try:
                os.remove(old_path)
            except Exception:
                pass

    # Save new face image crop in dataset/students/
    filename = f"student_{student.student_code}_{datetime.now().strftime('%Y%m%d%H%M%S')}.jpg"
    save_path = os.path.join(Config.STUDENT_DATASET_DIR, filename)
    cv2.imwrite(save_path, img_np)

    student.face_image_path = f"dataset/students/{filename}"
    student.encoding_json = encoding_json

    db.session.commit()

    has_face = encoding_json is not None
    return jsonify({
        'success': True,
        'message': 'Face photo captured and ' + ('encoding generated successfully!' if has_face else 'saved (Note: No face detected in photo, please retake in clear lighting).'),
        'has_face': has_face,
        'student': student.to_dict()
    })

# -------------------------------------------------------------------
# Live Attendance & AI Recognition Routes (Teacher)
# -------------------------------------------------------------------
@app.route('/api/sessions/start', methods=['POST'])
@token_required
def start_attendance_session(current_user):
    """
    Req 2 & 8: Teacher starts live attendance session.
    """
    data = request.get_json() or {}
    session_title = data.get('session_title', f"Class Session - {datetime.now().strftime('%b %d %H:%M')}")
    class_name = data.get('class_name', 'Computer Science - Year 4')

    session = AttendanceSession(
        session_title=session_title,
        class_name=class_name,
        created_by_teacher_id=current_user.id,
        created_by_teacher_name=current_user.full_name,
        status='IN_PROGRESS'
    )
    db.session.add(session)
    db.session.commit()

    # Pre-populate session records for all students in class as ABSENT initially
    class_students = Student.query.filter_by(class_name=class_name).all()
    for st in class_students:
        rec = AttendanceRecord(
            session_id=session.id,
            student_id=st.id,
            status='ABSENT',
            marking_method='AI_FACE_RECOGNITION',
            marked_by_teacher_name=None,
            approval_status='APPROVED'
        )
        db.session.add(rec)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Attendance session started',
        'session': session.to_dict()
    })

@app.route('/api/sessions/<int:session_id>/process_frame', methods=['POST'])
@token_required
def process_webcam_frame(current_user, session_id):
    """
    Req 4 & 7 & 8: Processes live webcam frame:
    - Runs AI face recognition against registered class students.
    - Reduces fakeness using live timestamping.
    - Saves unrecognized faces in dataset/undetected_faces/.
    - Marks matched students as PRESENT.
    """
    session = AttendanceSession.query.get(session_id)
    if not session or session.status != 'IN_PROGRESS':
        return jsonify({'success': False, 'message': 'Active session not found'}), 404

    data = request.get_json() or {}
    frame_b64 = data.get('frame')
    if not frame_b64:
        return jsonify({'success': False, 'message': 'Frame data missing'}), 400

    img_np = base64_to_cv2(frame_b64)
    if img_np is None:
        return jsonify({'success': False, 'message': 'Invalid frame format'}), 400

    class_students = Student.query.filter_by(class_name=session.class_name).all()

    # Automatically re-encode student face images stored in dataset/students/ if needed
    for st in class_students:
        if st.face_image_path:
            full_p = os.path.join(Config.DATA_DIR, st.face_image_path)
            if os.path.exists(full_p):
                needs_update = True
                if st.encoding_json:
                    try:
                        enc = json.loads(st.encoding_json)
                        if isinstance(enc, list) and len(enc) in (128, 256):
                            needs_update = False
                    except Exception:
                        pass
                if needs_update:
                    st_img = cv2.imread(full_p)
                    if st_img is not None:
                        faces = face_engine.detect_faces(st_img)
                        f_box = faces[0] if len(faces) > 0 else None
                        enc_new = face_engine.extract_encoding(st_img, f_box)
                        if enc_new:
                            st.encoding_json = json.dumps(enc_new)
                            db.session.commit()
    
    stamped_img, recognized, undetected = face_engine.process_live_frame(
        img_np, class_students, session_id, Config.UNDETECTED_FACES_DIR
    )

    # Encode processed stamped image back to base64 for frontend live stream
    _, buffer = cv2.imencode('.jpg', stamped_img)
    processed_b64 = base64.b64encode(buffer).decode('utf-8')

    # Save full snapped attendance photo to dataset/session_snapshots/ folder
    snapshot_filename = f"session_{session_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
    snapshot_filepath = os.path.join(Config.SESSION_SNAPSHOTS_DIR, snapshot_filename)
    cv2.imwrite(snapshot_filepath, stamped_img)
    snapshot_rel_path = f"dataset/session_snapshots/{snapshot_filename}"

    # Update database for recognized students
    newly_marked_present = []
    for match in recognized:
        st_id = match['student_id']
        rec = AttendanceRecord.query.filter_by(session_id=session.id, student_id=st_id).first()
        if rec and rec.status != 'PRESENT':
            rec.status = 'PRESENT'
            rec.marking_method = 'AI_FACE_RECOGNITION'
            rec.approval_status = 'APPROVED'
            rec.snapshot_path = snapshot_rel_path
            rec.timestamp = datetime.now()
            newly_marked_present.append(match['student_name'])

    # Save undetected faces to UndetectedFace table
    for u in undetected:
        u_face = UndetectedFace(
            session_id=session.id,
            image_path=u['image_path'],
            status='UNCLAIMED'
        )
        db.session.add(u_face)

    db.session.commit()

    return jsonify({
        'success': True,
        'processed_frame': f"data:image/jpeg;base64,{processed_b64}",
        'saved_snapshot_path': snapshot_rel_path,
        'recognized_count': len(recognized),
        'newly_marked_present': newly_marked_present,
        'undetected_count': len(undetected)
    })

@app.route('/api/sessions/<int:session_id>/complete', methods=['POST'])
@token_required
@admin_only
def complete_session(current_user, session_id):
    """
    Req 6: When attendance session ends, send parent email for all ABSENT students.
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404

    session.status = 'COMPLETED'
    session.completed_at = datetime.now()
    db.session.commit()

    # Find absent records where email has not been sent yet
    absent_records = AttendanceRecord.query.filter_by(
        session_id=session.id,
        status='ABSENT',
        email_sent=False
    ).all()

    emails_dispatched = 0
    date_str = session.completed_at.strftime('%d %b %Y, %I:%M %p')
    email_logs = []

    for r in absent_records:
        if r.student and r.student.parent_email:
            success, msg = send_parent_absent_email(
                parent_email=r.student.parent_email,
                student_name=r.student.name,
                roll_no=r.student.roll_no,
                class_name=session.class_name,
                date_str=date_str,
                teacher_name=session.created_by_teacher_name,
                student_code=r.student.student_code,
                session_title=session.session_title
            )
            email_logs.append({
                'student_name': r.student.name,
                'parent_email': r.student.parent_email,
                'success': success,
                'message': msg
            })
            if success:
                r.email_sent = True
                r.email_sent_at = datetime.now()
                emails_dispatched += 1

    db.session.commit()

    if emails_dispatched > 0:
        res_msg = f"Attendance finalized! Successfully delivered {emails_dispatched} parent absence email alerts via SMTP."
    elif len(absent_records) == 0:
        res_msg = "Attendance finalized! No absent students in this session."
    else:
        first_err = email_logs[0]['message'] if email_logs else "Email configuration issue."
        res_msg = f"Attendance finalized, BUT emails were NOT delivered. Reason: {first_err}"

    return jsonify({
        'success': True,
        'message': res_msg,
        'emails_dispatched': emails_dispatched,
        'email_logs': email_logs,
        'session': session.to_dict()
    })

# -------------------------------------------------------------------
# Undetected Face Claim & Teacher Manual Attendance (Req 9, 12, 13)
# -------------------------------------------------------------------
@app.route('/api/undetected', methods=['GET'])
@app.route('/api/undetected/<int:session_id>', methods=['GET'])
@token_required
def get_undetected_faces(current_user, session_id=None):
    """
    Req 9: Teacher can view undetected faces stored for a session or across all sessions.
    """
    if session_id:
        u_faces = UndetectedFace.query.filter_by(session_id=session_id).order_by(UndetectedFace.timestamp.desc()).all()
    else:
        u_faces = UndetectedFace.query.order_by(UndetectedFace.timestamp.desc()).all()

    return jsonify({
        'success': True,
        'undetected_faces': [u.to_dict() for u in u_faces]
    })

@app.route('/api/undetected/claim', methods=['POST'])
@token_required
def claim_undetected_face(current_user):
    """
    Req 9, 12, 13:
    - Teacher manually maps an undetected face snapshot to a student.
    - Records teacher's name.
    - Status set to PENDING_ADMIN for Admin approval workflow.
    """
    data = request.get_json() or {}
    undetected_id = data.get('undetected_id')
    student_id = data.get('student_id')

    if not undetected_id or not student_id:
        return jsonify({'success': False, 'message': 'Undetected face ID and Student ID are required'}), 400

    u_face = UndetectedFace.query.get(undetected_id)
    student = Student.query.get(student_id)

    if not u_face or not student:
        return jsonify({'success': False, 'message': 'Undetected face or student not found'}), 404

    # Update UndetectedFace record
    u_face.status = 'CLAIMED_PENDING'
    u_face.claimed_student_id = student.id
    u_face.claimed_by_teacher_name = current_user.full_name

    # Create/Update AttendanceRecord as MANUAL_TEACHER with PENDING_ADMIN status
    rec = AttendanceRecord.query.filter_by(session_id=u_face.session_id, student_id=student.id).first()
    if not rec:
        rec = AttendanceRecord(session_id=u_face.session_id, student_id=student.id)

    rec.status = 'PRESENT'
    rec.marking_method = 'MANUAL_TEACHER'
    rec.marked_by_teacher_name = current_user.full_name
    rec.approval_status = 'PENDING_ADMIN'
    rec.snapshot_path = u_face.image_path

    db.session.add(rec)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Manual attendance submitted for {student.name}. Request sent to Admin for approval.',
        'record': rec.to_dict()
    })

# -------------------------------------------------------------------
# Admin Approval Workflow Routes (Req 13)
# -------------------------------------------------------------------
@app.route('/api/admin/approvals', methods=['GET'])
@token_required
@admin_only
def get_pending_approvals(current_user):
    """
    Req 13: Admin views list of teacher manual attendance requests requiring approval.
    """
    pending_records = AttendanceRecord.query.filter_by(
        approval_status='PENDING_ADMIN'
    ).order_by(AttendanceRecord.timestamp.desc()).all()

    return jsonify({
        'success': True,
        'pending_approvals': [r.to_dict() for r in pending_records]
    })

@app.route('/api/admin/approvals/<int:record_id>/action', methods=['POST'])
@token_required
@admin_only
def handle_approval_action(current_user, record_id):
    """
    Req 13: Admin presses OK -> Approved (Marked PRESENT), otherwise REJECTED (Marked ABSENT).
    """
    data = request.get_json() or {}
    action = data.get('action') # 'APPROVE' or 'REJECT'

    rec = AttendanceRecord.query.get(record_id)
    if not rec:
        return jsonify({'success': False, 'message': 'Attendance record not found'}), 404

    if action == 'APPROVE':
        rec.approval_status = 'APPROVED'
        rec.status = 'PRESENT'
        msg = f"Manual attendance for {rec.student.name} APPROVED (Marked PRESENT)."
    else:
        rec.approval_status = 'REJECTED'
        rec.status = 'ABSENT'
        msg = f"Manual attendance for {rec.student.name} REJECTED (Marked ABSENT)."

    # Update associated UndetectedFace status if exists
    if rec.snapshot_path:
        u_face = UndetectedFace.query.filter_by(image_path=rec.snapshot_path).first()
        if u_face:
            u_face.status = 'APPROVED' if action == 'APPROVE' else 'REJECTED'

    u_faces = UndetectedFace.query.filter_by(session_id=rec.session_id, claimed_student_id=rec.student_id).all()
    for uf in u_faces:
        uf.status = 'APPROVED' if action == 'APPROVE' else 'REJECTED'

    db.session.commit()
    return jsonify({'success': True, 'message': msg, 'record': rec.to_dict()})

@app.route('/api/admin/undetected/<int:undetected_id>/action', methods=['POST'])
@token_required
@admin_only
def handle_undetected_claim_action(current_user, undetected_id):
    """
    Req 13: Admin approves or rejects a teacher manual face claim directly by undetected_id.
    """
    data = request.get_json() or {}
    action = data.get('action') # 'APPROVE' or 'REJECT'

    u_face = UndetectedFace.query.get(undetected_id)
    if not u_face:
        return jsonify({'success': False, 'message': 'Undetected face claim record not found'}), 404

    u_face.status = 'APPROVED' if action == 'APPROVE' else 'REJECTED'

    # Find associated AttendanceRecord
    rec = None
    if u_face.claimed_student_id:
        rec = AttendanceRecord.query.filter_by(
            session_id=u_face.session_id,
            student_id=u_face.claimed_student_id
        ).first()

    if not rec and u_face.image_path:
        rec = AttendanceRecord.query.filter_by(
            session_id=u_face.session_id,
            snapshot_path=u_face.image_path
        ).first()

    if rec:
        if action == 'APPROVE':
            rec.approval_status = 'APPROVED'
            rec.status = 'PRESENT'
        else:
            rec.approval_status = 'REJECTED'
            rec.status = 'ABSENT'

    db.session.commit()

    student_name = u_face.claimed_student.name if u_face.claimed_student else 'Student'
    status_str = 'APPROVED (Marked PRESENT)' if action == 'APPROVE' else 'REJECTED (Marked ABSENT)'
    return jsonify({
        'success': True,
        'message': f"Claim for {student_name} {status_str}.",
        'undetected_face': u_face.to_dict()
    })

# -------------------------------------------------------------------
# System Email Settings Routes (Admin & Teacher)
# -------------------------------------------------------------------
@app.route('/api/admin/settings/email', methods=['GET'])
@token_required
def get_email_settings(current_user):
    from email_service import get_smtp_config
    conf = get_smtp_config()
    # Mask password for security
    conf_masked = {
        'smtp_email': conf['smtp_email'],
        'has_password': bool(conf['smtp_password']),
        'enable_real_email': conf['enable_real_email']
    }
    return jsonify({'success': True, 'settings': conf_masked})

@app.route('/api/admin/settings/email', methods=['POST'])
@token_required
def update_email_settings(current_user):
    data = request.get_json() or {}
    smtp_email = data.get('smtp_email', '').strip()
    smtp_password = data.get('smtp_password', '').strip()
    enable_real = data.get('enable_real_email', False)

    if smtp_email:
        s_email = SystemSetting.query.filter_by(key='smtp_email').first()
        if not s_email:
            s_email = SystemSetting(key='smtp_email')
            db.session.add(s_email)
        s_email.value = smtp_email

    if smtp_password:
        s_pass = SystemSetting.query.filter_by(key='smtp_password').first()
        if not s_pass:
            s_pass = SystemSetting(key='smtp_password')
            db.session.add(s_pass)
        s_pass.value = smtp_password

    s_enable = SystemSetting.query.filter_by(key='enable_real_email').first()
    if not s_enable:
        s_enable = SystemSetting(key='enable_real_email')
        db.session.add(s_enable)
    s_enable.value = 'true' if enable_real else 'false'

    db.session.commit()
    return jsonify({'success': True, 'message': 'SMTP Email settings saved successfully.'})

@app.route('/api/admin/settings/test_email', methods=['POST'])
@token_required
def send_test_email(current_user):
    data = request.get_json() or {}
    target_email = data.get('target_email', current_user.email).strip()

    if not target_email:
        return jsonify({'success': False, 'message': 'Target email address required'}), 400

    success, msg = send_parent_absent_email(
        parent_email=target_email,
        student_name="Test Student",
        roll_no="TEST-001",
        class_name="System Test Class",
        date_str=datetime.now().strftime('%Y-%m-%d %H:%M'),
        teacher_name=current_user.full_name,
        force_test=True
    )

    return jsonify({'success': success, 'message': msg})

# -------------------------------------------------------------------
# Reports & Download Routes (Excel & PDF - Teacher + Admin) (Req 10 & 11)
# -------------------------------------------------------------------
@app.route('/api/sessions', methods=['GET'])
@token_required
def get_sessions(current_user):
    sessions = AttendanceSession.query.order_by(AttendanceSession.created_at.desc()).all()
    return jsonify({
        'success': True,
        'sessions': [s.to_dict() for s in sessions]
    })

@app.route('/api/sessions/<int:session_id>', methods=['GET'])
@token_required
def get_session_details(current_user, session_id):
    session = AttendanceSession.query.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404

    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    return jsonify({
        'success': True,
        'session': session.to_dict(),
        'records': [r.to_dict() for r in records]
    })

@app.route('/api/export/excel/<int:session_id>', methods=['GET'])
@token_required
def export_excel(current_user, session_id):
    """
    Req 10 & 11: Export session attendance to Excel file.
    Available to both Teacher and Admin.
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404

    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    filename = f"Attendance_Report_{session.class_name.replace(' ', '_')}_{session.id}.xlsx"
    file_path = os.path.join(Config.EXPORT_DIR, filename)

    export_attendance_to_excel(session, records, file_path)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/api/export/pdf/<int:session_id>', methods=['GET'])
@token_required
def export_pdf(current_user, session_id):
    """
    Req 10 & 11: Export session attendance to PDF file.
    Available to both Teacher and Admin.
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404

    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    filename = f"Attendance_Report_{session.class_name.replace(' ', '_')}_{session.id}.pdf"
    file_path = os.path.join(Config.EXPORT_DIR, filename)

    export_attendance_to_pdf(session, records, file_path)

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/pdf'
    )

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_DEBUG', 'False').lower() in ('true', '1', 't')
    app.run(host='0.0.0.0', port=port, debug=debug)
