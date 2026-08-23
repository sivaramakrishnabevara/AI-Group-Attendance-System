from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False) # 'ADMIN' or 'TEACHER'
    full_name = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'role': self.role,
            'full_name': self.full_name,
            'email': self.email,
            'created_at': self.created_at.strftime('%Y-%m-%d %I:%M:%S %p') if self.created_at else ''
        }

class Student(db.Model):
    __tablename__ = 'students'
    id = db.Column(db.Integer, primary_key=True)
    student_code = db.Column(db.String(50), unique=True, nullable=False)
    name = db.Column(db.String(120), nullable=False)
    roll_no = db.Column(db.String(50), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    parent_email = db.Column(db.String(120), nullable=False)
    parent_phone = db.Column(db.String(20), nullable=True)
    face_image_path = db.Column(db.String(255), nullable=True)
    encoding_json = db.Column(db.Text, nullable=True) # JSON stored array of float features
    created_at = db.Column(db.DateTime, default=datetime.now)

    def to_dict(self):
        return {
            'id': self.id,
            'student_code': self.student_code,
            'name': self.name,
            'roll_no': self.roll_no,
            'class_name': self.class_name,
            'parent_email': self.parent_email,
            'parent_phone': self.parent_phone,
            'face_image_path': self.face_image_path,
            'has_face': self.encoding_json is not None,
            'created_at': self.created_at.strftime('%Y-%m-%d %I:%M:%S %p') if self.created_at else ''
        }

class AttendanceSession(db.Model):
    __tablename__ = 'attendance_sessions'
    id = db.Column(db.Integer, primary_key=True)
    session_title = db.Column(db.String(150), nullable=False)
    class_name = db.Column(db.String(50), nullable=False)
    created_by_teacher_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_by_teacher_name = db.Column(db.String(120), nullable=False)
    status = db.Column(db.String(20), default='IN_PROGRESS') # 'IN_PROGRESS', 'COMPLETED'
    created_at = db.Column(db.DateTime, default=datetime.now)
    completed_at = db.Column(db.DateTime, nullable=True)

    records = db.relationship('AttendanceRecord', backref='session', lazy=True, cascade="all, delete-orphan")
    undetected = db.relationship('UndetectedFace', backref='session', lazy=True, cascade="all, delete-orphan")

    def to_dict(self):
        return {
            'id': self.id,
            'session_title': self.session_title,
            'class_name': self.class_name,
            'created_by_teacher_id': self.created_by_teacher_id,
            'created_by_teacher_name': self.created_by_teacher_name,
            'status': self.status,
            'created_at': self.created_at.strftime('%Y-%m-%d %I:%M:%S %p') if self.created_at else '',
            'completed_at': self.completed_at.strftime('%Y-%m-%d %I:%M:%S %p') if self.completed_at else None,
            'total_students': len(self.records),
            'present_count': len([r for r in self.records if r.status == 'PRESENT' and r.approval_status == 'APPROVED']),
            'absent_count': len([r for r in self.records if r.status == 'ABSENT']),
            'pending_approval_count': len([r for r in self.records if r.approval_status == 'PENDING_ADMIN'])
        }

class AttendanceRecord(db.Model):
    __tablename__ = 'attendance_records'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('attendance_sessions.id'), nullable=False)
    student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False) # 'PRESENT', 'ABSENT'
    marking_method = db.Column(db.String(30), nullable=False) # 'AI_FACE_RECOGNITION', 'MANUAL_TEACHER'
    marked_by_teacher_name = db.Column(db.String(120), nullable=True)
    approval_status = db.Column(db.String(30), nullable=False, default='APPROVED') # 'APPROVED', 'PENDING_ADMIN', 'REJECTED'
    snapshot_path = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    email_sent = db.Column(db.Boolean, default=False)
    email_sent_at = db.Column(db.DateTime, nullable=True)

    student = db.relationship('Student', backref=db.backref('attendance_records', cascade='all, delete-orphan'))

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'student_id': self.student_id,
            'student_name': self.student.name if self.student else 'Unknown',
            'roll_no': self.student.roll_no if self.student else 'N/A',
            'class_name': self.student.class_name if self.student else 'N/A',
            'parent_email': self.student.parent_email if self.student else 'N/A',
            'status': self.status,
            'marking_method': self.marking_method,
            'marked_by_teacher_name': self.marked_by_teacher_name,
            'approval_status': self.approval_status,
            'snapshot_path': self.snapshot_path,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %I:%M:%S %p') if self.timestamp else '',
            'email_sent': self.email_sent
        }

class UndetectedFace(db.Model):
    __tablename__ = 'undetected_faces'
    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.Integer, db.ForeignKey('attendance_sessions.id'), nullable=False)
    image_path = db.Column(db.String(255), nullable=False)
    timestamp = db.Column(db.DateTime, default=datetime.now)
    status = db.Column(db.String(30), default='UNCLAIMED') # 'UNCLAIMED', 'CLAIMED_PENDING', 'APPROVED', 'REJECTED'
    claimed_student_id = db.Column(db.Integer, db.ForeignKey('students.id'), nullable=True)
    claimed_by_teacher_name = db.Column(db.String(120), nullable=True)

    claimed_student = db.relationship('Student')

    def to_dict(self):
        return {
            'id': self.id,
            'session_id': self.session_id,
            'image_path': self.image_path,
            'timestamp': self.timestamp.strftime('%Y-%m-%d %I:%M:%S %p') if self.timestamp else '',
            'status': self.status,
            'claimed_student_id': self.claimed_student_id,
            'claimed_student_name': self.claimed_student.name if self.claimed_student else None,
            'claimed_by_teacher_name': self.claimed_by_teacher_name
        }

class SystemSetting(db.Model):
    __tablename__ = 'system_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'key': self.key,
            'value': self.value
        }
