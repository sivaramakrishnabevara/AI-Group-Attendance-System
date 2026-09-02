import os
import base64
import json
import jwt
from datetime import datetime, timedelta
from functools import wraps

from flask import Flask, request, jsonify, send_from_directory, send_file, Response
from flask_cors import CORS
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.middleware.proxy_fix import ProxyFix
import cv2
import numpy as np

from config import Config
from models import db, User, Student, AttendanceSession, AttendanceRecord, UndetectedFace, SystemSetting, EmailLog
from database import init_db
from face_engine import face_engine
from email_service import send_parent_absent_email, send_test_email, get_email_config, validate_email_address
from exporter import export_attendance_to_excel, export_attendance_to_pdf

app = Flask(__name__, static_folder='static', template_folder='templates')
app.config.from_object(Config)

# Enable ProxyFix for Render HTTPS reverse proxy
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_prefix=1)

allowed_origins = os.environ.get('ALLOWED_ORIGINS', '*').split(',')
if allowed_origins == ['*']:
    CORS(app, origins='*', supports_credentials=False)
else:
    CORS(app, origins=allowed_origins, supports_credentials=True)

# -------------------------------------------------------------------
# Custom JSON Error Handlers for Render API responses
# -------------------------------------------------------------------
@app.errorhandler(404)
def handle_404(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': f'API endpoint not found: {request.path}'}), 404
    return send_file('templates/index.html')

@app.errorhandler(405)
def handle_405(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': f'HTTP Method {request.method} not allowed for {request.path}'}), 405
    return send_file('templates/index.html')

@app.errorhandler(500)
def handle_500(e):
    if request.path.startswith('/api/'):
        return jsonify({'success': False, 'message': 'Internal Server Error. Please check server logs.'}), 500
    return send_file('templates/index.html')

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
            token = request.args.get('token')

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
    full_path = os.path.join(Config.DATA_DIR, 'dataset', filename)
    if os.path.exists(full_path):
        return send_from_directory(os.path.join(Config.DATA_DIR, 'dataset'), filename)
    
    # Persistent fallback if image file is missing from ephemeral Render container
    rel_path = f"dataset/{filename}"
    b64_data = None

    if filename.startswith('students/'):
        # Extract roll_no or filename search
        parts = filename.split('/')
        st = None
        if len(parts) >= 2:
            st = Student.query.filter(Student.roll_no == parts[1]).first()
        if not st:
            st = Student.query.filter((Student.face_image_path == rel_path) | (Student.face_image_path.endswith(filename))).first()
        if st and st.face_image_b64:
            try:
                parsed = json.loads(st.face_image_b64)
                if isinstance(parsed, list) and len(parsed) > 0:
                    idx = 0
                    if parts[-1].endswith('.jpg'):
                        num_part = parts[-1].replace('.jpg', '')
                        if num_part.isdigit():
                            idx = min(len(parsed) - 1, max(0, int(num_part) - 1))
                    b64_data = parsed[idx]
                elif isinstance(parsed, str):
                    b64_data = parsed
            except Exception:
                b64_data = st.face_image_b64
    elif filename.startswith('unknown_faces/') or filename.startswith('undetected_faces/'):
        uf = UndetectedFace.query.filter((UndetectedFace.image_path == rel_path) | (UndetectedFace.image_path.endswith(filename))).first()
        if uf and uf.image_b64:
            b64_data = uf.image_b64
    elif filename.startswith('session_snapshots/'):
        ar = AttendanceRecord.query.filter((AttendanceRecord.snapshot_path == rel_path) | (AttendanceRecord.snapshot_path.endswith(filename))).first()
        if ar and ar.snapshot_b64:
            b64_data = ar.snapshot_b64

    if b64_data:
        try:
            if ',' in b64_data:
                b64_data = b64_data.split(',')[1]
            img_bytes = base64.b64decode(b64_data)
            # Re-create file on ephemeral disk for subsequent reads
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            with open(full_path, 'wb') as f:
                f.write(img_bytes)
            return Response(img_bytes, mimetype='image/jpeg')
        except Exception:
            pass

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
    include_inactive = request.args.get('include_inactive', 'false').lower() in ('true', '1')
    query = Student.query
    if not include_inactive:
        query = query.filter_by(is_active=True)
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
    Creates a student and extracts face encodings from captured photo frames.
    Supports EXACTLY 5 face images stored under dataset/students/<ROLL_NUMBER>/01.jpg ... 05.jpg.
    Validates required Parent Mobile Number and single face detection per photo.
    """
    data = request.get_json() or {}
    name = data.get('name', '').strip()
    roll_no = data.get('roll_no', '').strip()
    class_name = data.get('class_name', '').strip()
    parent_phone = (data.get('parent_mobile_number') or data.get('parent_phone') or '').strip()
    parent_email = data.get('parent_email', '').strip()
    student_code = data.get('student_code', '').strip()
    
    face_images = data.get('face_images') # List of 5 base64 images
    single_face_image = data.get('face_image') # Single base64 image fallback

    if not all([name, roll_no, class_name, parent_email]):
        return jsonify({'success': False, 'message': 'Student Name, Roll Number, Class Name, and Parent Email are required'}), 400

    if not validate_email_address(parent_email):
        return jsonify({'success': False, 'message': 'Please enter a valid Parent Email address (e.g. parent@example.com)'}), 400

    existing_student = Student.query.filter_by(roll_no=roll_no, is_active=True).first()
    if existing_student:
        return jsonify({'success': False, 'message': f'Roll Number "{roll_no}" is already registered for active student {existing_student.name}.'}), 400

    norm_phone = ''
    if parent_phone:
        is_valid_phone, norm_phone = normalize_indian_mobile(parent_phone)
        if not is_valid_phone:
            norm_phone = parent_phone

    if not face_images or not isinstance(face_images, list) or len(face_images) != 5:
        return jsonify({'success': False, 'message': 'EXACTLY 5 face photo images are required to complete student registration.'}), 400

    image_list = face_images

    # Clean roll number for folder naming
    clean_roll = "".join(c for c in roll_no if c.isalnum() or c in ('-', '_')).strip() or f"roll_{roll_no}"
    student_dir = os.path.join(Config.STUDENT_DATASET_DIR, clean_roll)
    os.makedirs(student_dir, exist_ok=True)

    extracted_vectors = []
    saved_paths = []
    b64_list = []

    for idx, b64_img in enumerate(image_list):
        if not b64_img:
            return jsonify({'success': False, 'message': f'Photo #{idx + 1} is missing.'}), 400
        img_np = base64_to_cv2(b64_img)
        if img_np is None:
            return jsonify({'success': False, 'message': f'Invalid face photo format for image #{idx + 1}'}), 400

        faces = face_engine.detect_faces(img_np)
        if len(faces) == 0:
            return jsonify({'success': False, 'message': f'Face not detected in image #{idx + 1}. Please look directly at the camera.'}), 400
        if len(faces) > 1:
            return jsonify({'success': False, 'message': f'Multiple faces detected in image #{idx + 1}. Only one student should be in the camera.'}), 400

        encoding = face_engine.extract_encoding(img_np, faces[0])
        if not encoding:
            return jsonify({'success': False, 'message': f'Could not extract face embedding for image #{idx + 1}. Please retake with clear lighting.'}), 400

        extracted_vectors.append(encoding)
        b64_list.append(b64_img)

        filename = f"{idx + 1:02d}.jpg"
        file_path = os.path.join(student_dir, filename)
        cv2.imwrite(file_path, img_np)
        rel_path = f"dataset/students/{clean_roll}/{filename}"
        saved_paths.append(rel_path)

    if len(extracted_vectors) != 5:
        return jsonify({'success': False, 'message': f'EXACTLY 5 valid face photo encodings are required. Only {len(extracted_vectors)} valid encodings were generated.'}), 400

    encoding_json = json.dumps({
        'version': face_engine.MODEL_VERSION,
        'vectors': extracted_vectors,
        'vector': extracted_vectors[0]
    })

    face_b64_storage = json.dumps(b64_list)

    if not student_code:
        student_code = f"STU-{roll_no}"
        counter = 1
        base_code = student_code
        while Student.query.filter_by(student_code=student_code).first():
            student_code = f"{base_code}-{counter}"
            counter += 1
    elif Student.query.filter_by(student_code=student_code).first():
        return jsonify({'success': False, 'message': 'Student Code already registered'}), 400

    primary_rel_path = saved_paths[0] if saved_paths else f"dataset/students/{clean_roll}/01.jpg"

    student = Student(
        student_code=student_code,
        name=name,
        roll_no=roll_no,
        class_name=class_name,
        parent_email=parent_email,
        parent_phone=norm_phone,
        face_image_path=primary_rel_path,
        face_image_b64=face_b64_storage,
        encoding_json=encoding_json
    )
    try:
        db.session.add(student)
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        return jsonify({'success': False, 'message': f'Database error registering student: {str(e)}'}), 500

    return jsonify({
        'success': True,
        'message': f'Student registered successfully with 5 face photo encodings.',
        'student': student.to_dict()
    })

@app.route('/api/detect_face_check', methods=['POST'])
@token_required
def detect_face_check(current_user):
    """
    Validates face detection for a single captured photo during the 5-photo registration flow.
    Returns count: 0 (No face), 1 (Valid face), >= 2 (Multiple faces).
    """
    data = request.get_json() or {}
    b64_img = data.get('image')
    if not b64_img:
        return jsonify({'success': False, 'message': 'No image provided'}), 400

    img_np = base64_to_cv2(b64_img)
    if img_np is None:
        return jsonify({'success': False, 'message': 'Invalid image format'}), 400

    faces = face_engine.detect_faces(img_np)
    count = len(faces)

    if count == 0:
        msg = 'Face not detected. Please try again.'
    elif count > 1:
        msg = 'Multiple faces detected. Only one student should be in the camera.'
    else:
        msg = 'Face detected successfully.'

    return jsonify({
        'success': True,
        'count': count,
        'message': msg
    })

@app.route('/api/students/<int:student_id>', methods=['DELETE'])
@token_required
@admin_only
def delete_student(current_user, student_id):
    """
    Admin deactivates or deletes student.
    If historical attendance records exist, performs safe soft deactivation (is_active=False)
    so historical data is preserved while excluding student from future recognition.
    """
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    attendance_count = AttendanceRecord.query.filter_by(student_id=student_id).count()
    if attendance_count > 0:
        student.is_active = False
        db.session.commit()
        return jsonify({'success': True, 'message': f'Student {student.name} deactivated. Historical attendance preserved.'})

    if student.face_image_path:
        full_p = os.path.join(Config.DATA_DIR, student.face_image_path)
        if os.path.exists(full_p):
            try:
                os.remove(full_p)
            except Exception:
                pass

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
    """Admin can edit student details: name, roll_no, class_name, parent_phone, student_code."""
    student = Student.query.get(student_id)
    if not student:
        return jsonify({'success': False, 'message': 'Student not found'}), 404

    data = request.get_json() or {}
    student_code = data.get('student_code', '').strip()
    name = data.get('name', '').strip()
    roll_no = data.get('roll_no', '').strip()
    class_name = data.get('class_name', '').strip()
    parent_phone = (data.get('parent_mobile_number') or data.get('parent_phone') or '').strip()
    parent_email = data.get('parent_email', '').strip()

    if not all([name, roll_no, class_name, parent_email]):
        return jsonify({'success': False, 'message': 'Name, Roll Number, Class Name, and Parent Email are required'}), 400

    if not validate_email_address(parent_email):
        return jsonify({'success': False, 'message': 'Please enter a valid Parent Email address (e.g. parent@example.com)'}), 400

    norm_phone = student.parent_phone or ''
    if parent_phone:
        is_valid_phone, norm_phone = normalize_indian_mobile(parent_phone)
        if not is_valid_phone:
            norm_phone = parent_phone

    if student_code:
        existing = Student.query.filter(Student.student_code == student_code, Student.id != student_id).first()
        if existing:
            return jsonify({'success': False, 'message': 'Student code already used by another student'}), 400
        student.student_code = student_code

    student.name = name
    student.roll_no = roll_no
    student.class_name = class_name
    student.parent_email = parent_email
    if norm_phone:
        student.parent_phone = norm_phone
    if parent_email:
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
    f_box = faces[0] if len(faces) > 0 else None
    encoding_json = None
    encoding = face_engine.extract_encoding(img_np, f_box)
    if encoding:
        encoding_json = json.dumps({
            'version': face_engine.MODEL_VERSION,
            'vector': encoding
        })

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
    student.face_image_b64 = face_image_b64
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

    # Pre-populate session records for all active students in class as ABSENT initially
    class_students = Student.query.filter_by(class_name=class_name, is_active=True).all()
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

    class_students = Student.query.filter_by(class_name=session.class_name, is_active=True).all()

    # Automatically re-encode student face images if needed (supporting DB base64 fallback)
    for st in class_students:
        needs_update = False
        if not st.encoding_json:
            needs_update = True
        else:
            try:
                enc = json.loads(st.encoding_json)
                if isinstance(enc, dict):
                    if enc.get('version') != face_engine.MODEL_VERSION:
                        needs_update = True
                else:
                    needs_update = True
            except Exception:
                needs_update = True

        if needs_update:
            st_img = None
            if st.face_image_path:
                full_p = os.path.join(Config.DATA_DIR, st.face_image_path)
                if os.path.exists(full_p):
                    st_img = cv2.imread(full_p)
            if st_img is None and st.face_image_b64:
                st_img = base64_to_cv2(st.face_image_b64)

            if st_img is not None:
                faces = face_engine.detect_faces(st_img)
                f_box = faces[0] if len(faces) > 0 else None
                enc_new = face_engine.extract_encoding(st_img, f_box)
                if enc_new:
                    st.encoding_json = json.dumps({
                        'version': face_engine.MODEL_VERSION,
                        'vector': enc_new
                    })
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
            rec.snapshot_b64 = processed_b64
            rec.timestamp = datetime.now()
            newly_marked_present.append(match['student_name'])

    # Save undetected faces to UndetectedFace table
    for u in undetected:
        u_face = UndetectedFace(
            session_id=session.id,
            image_path=u['image_path'],
            image_b64=u.get('image_b64'),
            status='UNCLAIMED'
        )
        db.session.add(u_face)

    db.session.commit()

    import logging
    logger = logging.getLogger("face_recognition")
    logger.info(f"[LIVE FRAME] Session #{session_id} ({session.class_name}): active_students={len(class_students)}, recognized={len(recognized)}, undetected={len(undetected)}, threshold={face_engine.match_threshold}")

    return jsonify({
        'success': True,
        'processed_frame': f"data:image/jpeg;base64,{processed_b64}",
        'saved_snapshot_path': snapshot_rel_path,
        'recognized_count': len(recognized),
        'newly_marked_present': newly_marked_present,
        'undetected_count': len(undetected)
    })

@app.route('/api/sessions/<int:session_id>/diagnostics', methods=['GET'])
@token_required
def get_session_diagnostics(current_user, session_id):
    """
    Req 4: Development Diagnostic Endpoint
    Reports active students, encoding status, vector counts, threshold, and SFace model configuration.
    Secrets are strictly excluded.
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404

    class_students = Student.query.filter_by(class_name=session.class_name, is_active=True).all()
    students_info = []

    for st in class_students:
        s_vectors = face_engine._parse_vectors(st.encoding_json)
        students_info.append({
            'student_id': st.id,
            'name': st.name,
            'roll_no': st.roll_no,
            'class_name': st.class_name,
            'is_active': st.is_active,
            'has_encoding': len(s_vectors) > 0,
            'vectors_count': len(s_vectors),
            'has_image_path': bool(st.face_image_path),
            'has_image_b64': bool(st.face_image_b64)
        })

    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    present_count = len([r for r in records if r.status == 'PRESENT'])
    absent_count = len([r for r in records if r.status == 'ABSENT'])

    return jsonify({
        'success': True,
        'diagnostics': {
            'session_id': session.id,
            'session_title': session.session_title,
            'class_name': session.class_name,
            'session_status': session.status,
            'active_students_in_class': len(class_students),
            'total_session_records': len(records),
            'present_count': present_count,
            'absent_count': absent_count,
            'unknown_faces_count': len(session.undetected),
            'match_threshold': face_engine.match_threshold,
            'model_version': face_engine.MODEL_VERSION,
            'embedding_dim': face_engine.active_vector_dim,
            'students_info': students_info
        }
    })

@app.route('/api/sessions/<int:session_id>/submit_approval', methods=['POST'])
@token_required
def submit_session_approval(current_user, session_id):
    """
    Req 14: Teacher submits live attendance session for Admin approval.
    Status becomes SUBMITTED_FOR_APPROVAL.
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404

    session.status = 'SUBMITTED_FOR_APPROVAL'
    db.session.commit()

    return jsonify({
        'success': True,
        'message': 'Attendance session submitted for Admin approval.',
        'session': session.to_dict()
    })

@app.route('/api/sessions/<int:session_id>/complete', methods=['POST'])
@app.route('/api/sessions/<int:session_id>/finalize', methods=['POST'])
@token_required
def finalize_session_by_admin(current_user, session_id):
    """
    Admin finalizes attendance session permanently.
    1. Enforces ADMIN authorization.
    2. Approves valid claims, calculates ABSENT for remaining un-marked class students.
    3. Sets status to FINALIZED with timestamp and admin attribution.
    4. Dispatches Gmail parent absence emails ONLY for absent students.
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found'}), 404

    # Enforce strictly Admin role for finalization
    if current_user.role != 'ADMIN':
        return jsonify({'success': False, 'message': 'Authorization failed: Only Admin can finalize attendance sessions'}), 403

    if session.status == 'FINALIZED':
        return jsonify({
            'success': True,
            'message': 'Attendance session is already finalized.',
            'session': session.to_dict()
        })

    # Calculate present student IDs for this class session
    present_student_ids = set()
    for rec in session.records:
        if rec.status == 'PRESENT' and rec.approval_status == 'APPROVED':
            present_student_ids.add(rec.student_id)

    # Mark all missing registered active students in class as ABSENT
    class_students = Student.query.filter_by(class_name=session.class_name, is_active=True).all()
    for st in class_students:
        rec = AttendanceRecord.query.filter_by(session_id=session.id, student_id=st.id).first()
        if not rec:
            rec = AttendanceRecord(
                session_id=session.id,
                student_id=st.id,
                status='ABSENT',
                marking_method='AI_FACE_RECOGNITION',
                approval_status='APPROVED'
            )
            db.session.add(rec)
        elif rec.student_id not in present_student_ids:
            rec.status = 'ABSENT'
            rec.approval_status = 'APPROVED'

    session.status = 'FINALIZED'
    session.completed_at = datetime.now()
    session.finalized_by_admin_id = current_user.id
    session.finalized_by_admin_name = current_user.full_name
    db.session.commit()

    # Dispatch parent absence emails ONLY AFTER successful DB finalization
    absent_records = AttendanceRecord.query.filter_by(
        session_id=session.id,
        status='ABSENT',
        email_sent=False
    ).all()

    email_dispatched = 0
    date_str = session.completed_at.strftime('%d-%b-%Y')
    email_logs_res = []

    for r in absent_records:
        parent_email = r.student.parent_email if r.student else None
        if not r.student or not parent_email:
            st_info = r.student.name if r.student else f"Student ID {r.student_id}"
            import logging
            logging.getLogger("app").warning(f"Parent email missing for student {st_info}")
            continue

        success, msg, details = send_parent_absent_email(
            parent_email=parent_email,
            student_name=r.student.name,
            roll_no=r.student.roll_no,
            class_name=session.class_name,
            date_str=date_str,
            teacher_name=session.created_by_teacher_name,
            session_title=session.session_title,
            session_id=session.id,
            student_id=r.student_id
        )
        email_logs_res.append({
            'student_name': r.student.name,
            'parent_email': parent_email,
            'success': success,
            'message': msg
        })
        if success:
            r.email_sent = True
            r.email_sent_at = datetime.now()
            email_dispatched += 1

    db.session.commit()

    if email_dispatched > 0:
        res_msg = f"Attendance finalized! Successfully sent {email_dispatched} parent absence email notifications."
    elif len(absent_records) == 0:
        res_msg = "Attendance finalized! All registered students were present."
    else:
        first_info = email_logs_res[0]['message'] if email_logs_res else "Resend HTTPS Email API credentials missing or invalid."
        res_msg = f"Attendance finalized. Parent Email status: {first_info}"

    return jsonify({
        'success': True,
        'message': res_msg,
        'email_dispatched': email_dispatched,
        'email_logs': email_logs_res,
        'session': session.to_dict()
    })

# -------------------------------------------------------------------
# Unknown Faces & Teacher Assignment / Admin Approval Routes
# -------------------------------------------------------------------
@app.route('/api/unknown_faces', methods=['GET'])
@app.route('/api/admin/approvals', methods=['GET'])
@app.route('/api/undetected/<int:session_id>', methods=['GET'])
@token_required
def get_unknown_faces(current_user, session_id=None):
    query = UndetectedFace.query
    if session_id:
        query = query.filter_by(session_id=session_id)
    faces = query.order_by(UndetectedFace.timestamp.desc()).all()
    return jsonify({
        'success': True,
        'unknown_faces': [f.to_dict() for f in faces],
        'undetected_faces': [f.to_dict() for f in faces]
    })

@app.route('/api/teacher/assign_unknown_face', methods=['POST'])
@token_required
def teacher_assign_unknown_face(current_user):
    """
    Req 12: Teacher manually assigns unknown face image to a student.
    Status becomes 'Pending Admin Approval' (PENDING_ADMIN).
    """
    data = request.get_json() or {}
    undetected_id = data.get('undetected_id') or data.get('unknown_face_id')
    student_id = data.get('student_id')

    if not undetected_id or not student_id:
        return jsonify({'success': False, 'message': 'Unknown face ID and Student ID are required'}), 400

    u_face = UndetectedFace.query.get(undetected_id)
    student = Student.query.get(student_id)

    if not u_face or not student:
        return jsonify({'success': False, 'message': 'Unknown face crop or Student record not found'}), 404

    u_face.claimed_student_id = student.id
    u_face.claimed_by_teacher_name = current_user.full_name
    u_face.status = 'PENDING_ADMIN'

    # Create/update attendance record in PENDING_ADMIN state
    rec = AttendanceRecord.query.filter_by(session_id=u_face.session_id, student_id=student.id).first()
    if not rec:
        rec = AttendanceRecord(
            session_id=u_face.session_id,
            student_id=student.id,
            status='PRESENT',
            marking_method='MANUAL_TEACHER',
            marked_by_teacher_name=current_user.full_name,
            approval_status='PENDING_ADMIN',
            snapshot_path=u_face.image_path,
            snapshot_b64=u_face.image_b64
        )
        db.session.add(rec)
    else:
        rec.status = 'PRESENT'
        rec.marking_method = 'MANUAL_TEACHER'
        rec.marked_by_teacher_name = current_user.full_name
        rec.approval_status = 'PENDING_ADMIN'
        rec.snapshot_path = u_face.image_path
        rec.snapshot_b64 = u_face.image_b64

    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'Assigned unknown face to {student.name}. Submitted for Admin approval (Pending Admin Approval).',
        'unknown_face': u_face.to_dict()
    })

@app.route('/api/admin/unknown_faces/<int:undetected_id>/action', methods=['POST'])
@app.route('/api/admin/undetected/<int:undetected_id>/action', methods=['POST'])
@app.route('/api/admin/approvals/<int:undetected_id>/action', methods=['POST'])
@token_required
@admin_only
def admin_unknown_face_action(current_user, undetected_id):
    """
    Req 13: Admin approves or rejects teacher unknown-face assignment.
    """
    data = request.get_json() or {}
    action = (data.get('action') or '').upper()

    if action not in ('APPROVE', 'REJECT'):
        return jsonify({'success': False, 'message': 'Action must be APPROVE or REJECT'}), 400

    u_face = UndetectedFace.query.get(undetected_id)
    if not u_face:
        return jsonify({'success': False, 'message': 'Unknown face record not found'}), 404

    if action == 'APPROVE':
        u_face.status = 'APPROVED'
        if u_face.claimed_student_id:
            rec = AttendanceRecord.query.filter_by(session_id=u_face.session_id, student_id=u_face.claimed_student_id).first()
            if rec:
                rec.status = 'PRESENT'
                rec.approval_status = 'APPROVED'
        msg = 'Unknown face assignment APPROVED. Attendance marked PRESENT.'
    else:
        u_face.status = 'REJECTED'
        if u_face.claimed_student_id:
            rec = AttendanceRecord.query.filter_by(session_id=u_face.session_id, student_id=u_face.claimed_student_id).first()
            if rec:
                rec.status = 'ABSENT'
                rec.approval_status = 'REJECTED'
        msg = 'Unknown face assignment REJECTED. Attendance not marked present.'

    db.session.commit()

    return jsonify({
        'success': True,
        'message': msg,
        'unknown_face': u_face.to_dict()
    })

# -------------------------------------------------------------------
# System SMS Settings Routes (Admin Only)
# -------------------------------------------------------------------
@app.route('/api/admin/settings/sms', methods=['GET'])
@token_required
@admin_only
def get_sms_settings_route(current_user):
    conf = get_sms_config()
    return jsonify({'success': True, 'settings': conf})

@app.route('/api/admin/settings/sms', methods=['POST'])
@token_required
@admin_only
def update_sms_settings_route(current_user):
    data = request.get_json() or {}
    sms_mode = data.get('sms_mode', 'SIMULATION').strip().upper()
    sms_provider = data.get('sms_provider', 'GENERIC_HTTP').strip()
    sms_api_key = data.get('sms_api_key', '').strip()
    sms_api_secret = data.get('sms_api_secret', '').strip()
    sms_sender_id = data.get('sms_sender_id', 'ATTNDS').strip()
    sms_http_url = data.get('sms_http_url', '').strip()
    sms_route = data.get('sms_route', 'q').strip()
    sms_dlt_te_id = data.get('sms_dlt_te_id', '').strip()
    sms_enabled = data.get('sms_enabled', True)

    settings_map = {
        'sms_mode': sms_mode,
        'sms_provider': sms_provider,
        'sms_api_key': sms_api_key,
        'sms_api_secret': sms_api_secret,
        'sms_sender_id': sms_sender_id,
        'sms_http_url': sms_http_url,
        'sms_route': sms_route,
        'sms_dlt_te_id': sms_dlt_te_id,
        'sms_enabled': 'true' if sms_enabled else 'false'
    }

    for key, val in settings_map.items():
        if val is not None:
            s_obj = SystemSetting.query.filter_by(key=key).first()
            if not s_obj:
                s_obj = SystemSetting(key=key)
                db.session.add(s_obj)
            s_obj.value = str(val)

    db.session.commit()
    return jsonify({'success': True, 'message': 'SMS settings saved successfully.'})

@app.route('/api/admin/sms_logs', methods=['GET'])
@token_required
@admin_only
def get_sms_logs_route(current_user):
    logs = SMSLog.query.order_by(SMSLog.timestamp.desc()).limit(200).all()
    return jsonify({
        'success': True,
        'logs': [l.to_dict() for l in logs]
    })

@app.route('/api/admin/settings/email', methods=['GET'])
@token_required
@admin_only
def get_email_settings_route(current_user):
    conf = get_email_config()
    conf_safe = dict(conf)
    if conf_safe.get('gmail_app_password'):
        conf_safe['gmail_app_password_masked'] = "••••••••••••••••"
    if conf_safe.get('email_api_key'):
        conf_safe['email_api_key_masked'] = "••••••••••••••••"
    return jsonify({'success': True, 'settings': conf_safe})

@app.route('/api/admin/settings/email', methods=['POST'])
@token_required
@admin_only
def update_email_settings_route(current_user):
    data = request.get_json() or {}
    enable_email = data.get('enable_email_alerts', True)
    email_mode = str(data.get('email_mode', 'API')).strip().upper()
    email_provider = str(data.get('email_provider', 'RESEND')).strip().upper()
    email_api_key = str(data.get('email_api_key', '')).strip()
    email_from = str(data.get('email_from', '')).strip()
    gmail_email = str(data.get('gmail_email', '')).strip()
    gmail_app_password = str(data.get('gmail_app_password', '')).strip()

    if email_from and not validate_email_address(email_from):
        return jsonify({'success': False, 'message': 'Invalid sender email address syntax'}), 400
    if gmail_email and not validate_email_address(gmail_email):
        return jsonify({'success': False, 'message': 'Invalid Gmail email address syntax'}), 400

    settings_map = {
        'enable_email_alerts': 'true' if enable_email else 'false',
        'email_mode': email_mode,
        'email_provider': email_provider,
        'email_from': email_from,
        'gmail_email': gmail_email
    }

    if email_api_key and email_api_key != "••••••••••••••••":
        settings_map['email_api_key'] = email_api_key
    if gmail_app_password and gmail_app_password != "••••••••••••••••":
        settings_map['gmail_app_password'] = gmail_app_password

    for key, val in settings_map.items():
        s_obj = SystemSetting.query.filter_by(key=key).first()
        if not s_obj:
            s_obj = SystemSetting(key=key)
            db.session.add(s_obj)
        s_obj.value = str(val)

    db.session.commit()
    return jsonify({'success': True, 'message': 'Email configuration settings saved successfully.'})

@app.route('/api/admin/email_logs', methods=['GET'])
@token_required
@admin_only
def get_email_logs_route(current_user):
    logs = EmailLog.query.order_by(EmailLog.timestamp.desc()).limit(200).all()
    return jsonify({
        'success': True,
        'logs': [l.to_dict() for l in logs]
    })

@app.route('/api/admin/settings/test_email', methods=['POST'])
@token_required
@admin_only
def send_test_email_route(current_user):
    data = request.get_json() or {}
    target_email = (data.get('email') or data.get('target_email') or '').strip()
    if not target_email:
        return jsonify({'success': False, 'message': 'Target email address is required'}), 400
    if not validate_email_address(target_email):
        return jsonify({'success': False, 'message': 'Invalid recipient email.'}), 400

    success, msg, details = send_test_email(target_email, current_user.full_name)
    return jsonify({
        'success': success,
        'message': msg,
        'details': details
    })

@app.route('/api/analytics', methods=['GET'])
@token_required
def get_analytics(current_user):
    """
    Returns attendance analytics:
    - Total Students
    - Average Attendance %
    - Total Present Count, Absent Count
    - Class-wise breakdown
    - Risk distribution (Low >=85%, Medium 75-84%, High <75%)
    """
    active_students = Student.query.filter_by(is_active=True).all()
    total_students = len(active_students)
    
    finalized_sessions = AttendanceSession.query.filter_by(status='FINALIZED').all()
    total_finalized_sessions = len(finalized_sessions)
    
    student_stats = []
    low_risk = 0
    med_risk = 0
    high_risk = 0
    
    class_totals = {}
    class_presents = {}
    
    total_present_records = 0
    total_absent_records = 0
    
    for st in active_students:
        recs = AttendanceRecord.query.filter_by(student_id=st.id).all()
        finalized_recs = [r for r in recs if r.session and r.session.status == 'FINALIZED']
        total_st_recs = len(finalized_recs)
        present_st_recs = len([r for r in finalized_recs if r.status == 'PRESENT'])
        absent_st_recs = len([r for r in finalized_recs if r.status == 'ABSENT'])
        
        total_present_records += present_st_recs
        total_absent_records += absent_st_recs
        
        rate = round((present_st_recs / total_st_recs * 100), 1) if total_st_recs > 0 else 100.0
        
        if rate >= 85.0:
            low_risk += 1
            risk = 'LOW_RISK'
        elif rate >= 75.0:
            med_risk += 1
            risk = 'MEDIUM_RISK'
        else:
            high_risk += 1
            risk = 'HIGH_RISK'
            
        c_name = st.class_name or 'General'
        class_totals[c_name] = class_totals.get(c_name, 0) + total_st_recs
        class_presents[c_name] = class_presents.get(c_name, 0) + present_st_recs
        
        student_stats.append({
            'student_id': st.id,
            'name': st.name,
            'roll_no': st.roll_no,
            'class_name': st.class_name,
            'rate': rate,
            'risk': risk
        })
        
    avg_attendance = round(sum(s['rate'] for s in student_stats) / len(student_stats), 1) if student_stats else 0.0
    
    class_breakdown = {}
    for c_name, tot in class_totals.items():
        class_breakdown[c_name] = round((class_presents[c_name] / tot * 100), 1) if tot > 0 else 0.0

    return jsonify({
        'success': True,
        'analytics': {
            'total_students': total_students,
            'total_sessions': total_finalized_sessions,
            'average_attendance': avg_attendance,
            'total_present_records': total_present_records,
            'total_absent_records': total_absent_records,
            'risk_distribution': {
                'low_risk': low_risk,
                'medium_risk': med_risk,
                'high_risk': high_risk
            },
            'class_breakdown': class_breakdown,
            'student_stats': student_stats
        }
    })

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
@app.route('/api/sessions/<int:session_id>/export/excel', methods=['GET'])
@token_required
def export_excel(current_user, session_id):
    """
    Export session attendance to Excel file (.xlsx).
    Available to both Professor and Admin.
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found.'}), 404

    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    filename = f"attendance_session_{session.id}.xlsx"
    file_path = os.path.join(Config.EXPORT_DIR, filename)

    try:
        export_attendance_to_excel(session, records, file_path)
    except Exception as e:
        return jsonify({'success': False, 'message': 'Unable to generate report. Please try again.'}), 500

    return send_file(
        file_path,
        as_attachment=True,
        download_name=filename,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

@app.route('/api/export/pdf/<int:session_id>', methods=['GET'])
@app.route('/api/sessions/<int:session_id>/export/pdf', methods=['GET'])
@token_required
def export_pdf(current_user, session_id):
    """
    Export session attendance to PDF file (.pdf).
    Available to both Professor and Admin.
    """
    session = AttendanceSession.query.get(session_id)
    if not session:
        return jsonify({'success': False, 'message': 'Session not found.'}), 404

    records = AttendanceRecord.query.filter_by(session_id=session.id).all()
    filename = f"attendance_session_{session.id}.pdf"
    file_path = os.path.join(Config.EXPORT_DIR, filename)

    try:
        export_attendance_to_pdf(session, records, file_path)
    except Exception as e:
        return jsonify({'success': False, 'message': 'Unable to generate report. Please try again.'}), 500

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
