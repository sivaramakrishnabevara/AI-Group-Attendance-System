import cv2
import numpy as np
import os
import uuid
import json
from datetime import datetime
from PIL import Image

try:
    import face_recognition
    HAS_DEEP_RECOGNITION = True
except Exception:
    HAS_DEEP_RECOGNITION = False

class FaceEngine:
    def __init__(self, match_threshold=0.45):
        # Default match threshold 0.45 for ResNet 128-D (corresponds to max Euclidean distance <= 0.55)
        self.match_threshold = match_threshold
        self.active_vector_dim = 128 if HAS_DEEP_RECOGNITION else 256
        # Load Haar Cascade from OpenCV default data
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

    def detect_faces(self, image_np):
        """
        Detects faces in an RGB or BGR numpy image array.
        Returns list of (x, y, w, h) bounding boxes.
        """
        if image_np is None or image_np.size == 0:
            return []
        
        # Use face_recognition HOG detector if available, fallback to Haar Cascade
        if HAS_DEEP_RECOGNITION:
            try:
                rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
                locs = face_recognition.face_locations(rgb, model='hog')
                if len(locs) > 0:
                    # Convert (top, right, bottom, left) -> (x, y, w, h)
                    return [(left, top, right - left, bottom - top) for (top, right, bottom, left) in locs]
            except Exception:
                pass

        gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY)
        gray = cv2.equalizeHist(gray)
        
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        return faces

    def extract_encoding(self, image_np, face_box=None):
        """
        Extracts 128-d ResNet Deep Learning Face Encoding via face_recognition library,
        or 256-d normalized LBP vector as fallback.
        """
        if image_np is None or image_np.size == 0:
            return None

        # 1. Try Deep Learning ResNet 128-D vector extraction
        if HAS_DEEP_RECOGNITION:
            try:
                rgb = cv2.cvtColor(image_np, cv2.COLOR_BGR2RGB)
                if face_box is not None:
                    x, y, w, h = face_box
                    top = max(0, int(y))
                    right = min(image_np.shape[1], int(x + w))
                    bottom = min(image_np.shape[0], int(y + h))
                    left = max(0, int(x))
                    encs = face_recognition.face_encodings(rgb, [(top, right, bottom, left)])
                else:
                    encs = face_recognition.face_encodings(rgb)
                
                if len(encs) > 0:
                    return [float(val) for val in encs[0]]
            except Exception:
                pass

        # 2. Fallback crop preparation for LBP vector
        if face_box is not None:
            x, y, w, h = face_box
            margin_x = int(w * 0.1)
            margin_y = int(h * 0.1)
            h_img, w_img = image_np.shape[:2]
            
            x1 = max(0, int(x - margin_x))
            y1 = max(0, int(y - margin_y))
            x2 = min(w_img, int(x + w + margin_x))
            y2 = min(h_img, int(y + h + margin_y))
            
            face_crop = image_np[y1:y2, x1:x2]
        else:
            face_crop = image_np

        if face_crop is None or face_crop.size == 0:
            return None

        # 3. Fallback to 256-D Normalized LBP Vector
        gray = cv2.cvtColor(face_crop, cv2.COLOR_BGR2GRAY) if len(face_crop.shape) == 3 else face_crop
        gray = cv2.resize(gray, (128, 128))
        gray = cv2.equalizeHist(gray)

        c = gray[1:-1, 1:-1]
        lbp = np.zeros_like(c, dtype=np.uint8)
        lbp |= ((gray[:-2, :-2] >= c) << 7).astype(np.uint8)
        lbp |= ((gray[:-2, 1:-1] >= c) << 6).astype(np.uint8)
        lbp |= ((gray[:-2, 2:]   >= c) << 5).astype(np.uint8)
        lbp |= ((gray[1:-1, 2:]  >= c) << 4).astype(np.uint8)
        lbp |= ((gray[2:, 2:]    >= c) << 3).astype(np.uint8)
        lbp |= ((gray[2:, 1:-1]  >= c) << 2).astype(np.uint8)
        lbp |= ((gray[2:, :-2]   >= c) << 1).astype(np.uint8)
        lbp |= ((gray[1:-1, :-2] >= c) << 0).astype(np.uint8)

        cell_h, cell_w = lbp.shape[0] // 4, lbp.shape[1] // 4
        hists = []
        for r in range(4):
            for c_idx in range(4):
                cell = lbp[r*cell_h:(r+1)*cell_h, c_idx*cell_w:(c_idx+1)*cell_w]
                hist, _ = np.histogram(cell, bins=16, range=(0, 256))
                hist = hist.astype(np.float32)
                s = np.sum(hist)
                if s > 0:
                    hist /= s
                hists.append(hist)

        res = np.concatenate(hists)
        return [float(val) for val in res]

    def compute_similarity(self, encoding1, encoding2):
        """
        Computes similarity score (0.0 to 1.0) using Euclidean Distance (for ResNet 128D)
        or Bhattacharyya/Cosine measure (for LBP 256D).
        """
        if not encoding1 or not encoding2:
            return 0.0
        
        try:
            v1 = np.array(encoding1, dtype=np.float32)
            v2 = np.array(encoding2, dtype=np.float32)
        except Exception:
            return 0.0

        if v1.size == 0 or v2.size == 0 or len(v1) != len(v2):
            return 0.0

        if len(v1) == 128:
            # ResNet 128-D Euclidean Distance matching
            # distance d in [0.0, 1.0+]. Similarity = 1.0 - d.
            dist = float(np.linalg.norm(v1 - v2))
            sim = max(0.0, min(1.0, 1.0 - dist))
            return sim
        elif len(v1) == 256:
            # LBP 256-D Bhattacharyya / Cosine Matching
            v1_sqrt = np.sqrt(np.maximum(v1, 0.0))
            v2_sqrt = np.sqrt(np.maximum(v2, 0.0))
            norm1 = np.linalg.norm(v1_sqrt)
            norm2 = np.linalg.norm(v2_sqrt)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            cosine_sim = float(np.dot(v1_sqrt, v2_sqrt) / (norm1 * norm2))
            return max(0.0, min(1.0, cosine_sim))
        else:
            # Generic Cosine Similarity
            norm1 = np.linalg.norm(v1)
            norm2 = np.linalg.norm(v2)
            if norm1 == 0 or norm2 == 0:
                return 0.0
            cosine_sim = float(np.dot(v1, v2) / (norm1 * norm2))
            return max(0.0, min(1.0, cosine_sim))

    def add_anti_spoof_timestamp(self, image_np, client_timestamp=None):
        """
        Overlays live anti-spoofing timestamp watermark directly on the image frame.
        """
        stamped_img = image_np.copy()
        h, w = stamped_img.shape[:2]
        
        server_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        time_text = f"LIVE STAMP: {server_time} | SYNC"
        
        banner_h = int(h * 0.08)
        overlay = stamped_img.copy()
        cv2.rectangle(overlay, (0, h - banner_h), (w, h), (15, 23, 42), -1)
        cv2.addWeighted(overlay, 0.7, stamped_img, 0.3, 0, stamped_img)
        
        cv2.putText(
            stamped_img,
            time_text,
            (15, h - int(banner_h * 0.3)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            (0, 230, 118), # Neon Emerald
            1,
            cv2.LINE_AA
        )
        return stamped_img

    def process_live_frame(self, image_np, student_records, session_id, undetected_folder):
        """
        Processes a live video frame:
        1. Detects all faces.
        2. Compares face encodings with registered students (enforcing unique student assignment per frame).
        3. Returns recognized students.
        4. Saves undetected/unregistered faces into undetected_folder for teacher manual mapping.
        """
        stamped_img = self.add_anti_spoof_timestamp(image_np)
        faces = self.detect_faces(image_np)
        
        recognized_results = []
        undetected_saved = []

        h_img, w_img = image_np.shape[:2]
        assigned_student_ids = set()

        # Dynamic match threshold based on encoding type
        effective_threshold = self.match_threshold if self.active_vector_dim == 128 else 0.80

        for (x, y, w, h) in faces:
            encoding = self.extract_encoding(image_np, (x, y, w, h))
            if not encoding:
                continue
            
            best_match_student = None
            highest_sim = 0.0
            
            for student in student_records:
                if not student.encoding_json:
                    continue
                # Prevent duplicate assignment of the same student to multiple faces in one picture
                if student.id in assigned_student_ids:
                    continue
                try:
                    s_encoding = json.loads(student.encoding_json)
                    if not isinstance(s_encoding, list):
                        continue
                    sim = self.compute_similarity(encoding, s_encoding)
                    if sim > highest_sim:
                        highest_sim = sim
                        best_match_student = student
                except Exception:
                    continue
            
            # Check match against effective threshold
            if best_match_student and highest_sim >= effective_threshold:
                assigned_student_ids.add(best_match_student.id)
                recognized_results.append({
                    'student_id': best_match_student.id,
                    'student_code': best_match_student.student_code,
                    'student_name': best_match_student.name,
                    'roll_no': best_match_student.roll_no,
                    'class_name': best_match_student.class_name,
                    'confidence': round(highest_sim * 100, 1),
                    'bbox': [int(x), int(y), int(w), int(h)]
                })
                # Draw Green box for recognized face
                cv2.rectangle(stamped_img, (x, y), (x + w, y + h), (0, 230, 118), 2)
                cv2.putText(stamped_img, f"{best_match_student.name} ({round(highest_sim*100)}%)", 
                            (x, max(y - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 230, 118), 2)
            else:
                # Undetected/Unrecognized Person Face!
                margin = int(w * 0.25)
                x1 = max(0, x - margin)
                y1 = max(0, y - margin)
                x2 = min(w_img, x + w + margin)
                y2 = min(h_img, y + h + margin)
                
                crop = stamped_img[y1:y2, x1:x2]
                
                if crop.size > 0:
                    filename = f"session_{session_id}_{uuid.uuid4().hex[:8]}.jpg"
                    filepath = os.path.join(undetected_folder, filename)
                    cv2.imwrite(filepath, crop)
                    
                    rel_path = f"dataset/undetected_faces/{filename}"
                    undetected_saved.append({
                        'image_path': rel_path,
                        'bbox': [int(x), int(y), int(w), int(h)]
                    })
                    
                # Draw Red box for unrecognized face
                cv2.rectangle(stamped_img, (x, y), (x + w, y + h), (255, 61, 0), 2)
                cv2.putText(stamped_img, "UNKNOWN / UNREGISTERED", 
                            (x, max(y - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 61, 0), 2)

        return stamped_img, recognized_results, undetected_saved

face_engine = FaceEngine(match_threshold=0.45)

