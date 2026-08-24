import cv2
import numpy as np
import os
import uuid
import json
import urllib.request
from datetime import datetime

# ONNX model directory and paths
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'models')
YUNET_MODEL_PATH = os.path.join(MODEL_DIR, 'face_detection_yunet_2023mar.onnx')
SFACE_MODEL_PATH = os.path.join(MODEL_DIR, 'face_recognition_sface_2021dec.onnx')

YUNET_URL = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_detection_yunet/face_detection_yunet_2023mar.onnx'
SFACE_URL = 'https://github.com/opencv/opencv_zoo/raw/main/models/face_recognition_sface/face_recognition_sface_2021dec.onnx'

MODEL_VERSION = "SFACE_ONNX_V1"

def ensure_onnx_models():
    """
    Ensures that YuNet and SFace ONNX model files exist in the models/ directory.
    Downloads them automatically if missing.
    """
    os.makedirs(MODEL_DIR, exist_ok=True)
    if not os.path.exists(YUNET_MODEL_PATH) or os.path.getsize(YUNET_MODEL_PATH) < 10000:
        print(f"Downloading YuNet ONNX model to {YUNET_MODEL_PATH}...")
        urllib.request.urlretrieve(YUNET_URL, YUNET_MODEL_PATH)
    if not os.path.exists(SFACE_MODEL_PATH) or os.path.getsize(SFACE_MODEL_PATH) < 10000:
        print(f"Downloading SFace ONNX model to {SFACE_MODEL_PATH}...")
        urllib.request.urlretrieve(SFACE_URL, SFACE_MODEL_PATH)

class FaceEngine:
    def __init__(self, match_threshold=0.40):
        # Match threshold 0.40 for SFace Cosine Similarity (Range: 0.0 to 1.0)
        self.match_threshold = match_threshold
        self.active_vector_dim = 128
        self.MODEL_VERSION = MODEL_VERSION

        # Ensure ONNX models exist
        ensure_onnx_models()

        # Load SFace Recognizer ONNX model once at app startup
        self.recognizer = cv2.FaceRecognizerSF.create(SFACE_MODEL_PATH, "")

        # Haar Cascade detector fallback
        cascade_path = cv2.data.haarcascades + 'haarcascade_frontalface_default.xml'
        self.face_cascade = cv2.CascadeClassifier(cascade_path)

        # Cache detector instances for image resolutions to prevent re-instantiation overhead
        self._detector_cache = {}

    def _get_detector(self, width, height):
        key = (width, height)
        if key not in self._detector_cache:
            detector = cv2.FaceDetectorYN.create(
                YUNET_MODEL_PATH,
                "",
                (width, height),
                score_threshold=0.5,
                nms_threshold=0.3,
                top_k=5000
            )
            self._detector_cache[key] = detector
            if len(self._detector_cache) > 20:
                self._detector_cache.pop(next(iter(self._detector_cache)))
        return self._detector_cache[key]

    def _parse_vector(self, encoding):
        """
        Safely extracts float vector list from raw list, JSON string, or dict structure.
        """
        if not encoding:
            return None
        if isinstance(encoding, str):
            try:
                encoding = json.loads(encoding)
            except Exception:
                return None
        if isinstance(encoding, dict):
            if 'vector' in encoding and isinstance(encoding['vector'], list):
                return encoding['vector']
            if 'vectors' in encoding and isinstance(encoding['vectors'], list) and len(encoding['vectors']) > 0:
                return encoding['vectors'][0]
            return []
        if isinstance(encoding, list):
            if len(encoding) > 0 and isinstance(encoding[0], list):
                return encoding[0]
            return encoding
        return None

    def _parse_vectors(self, encoding):
        """
        Safely extracts list of 128-D float vector arrays from raw list, JSON string, or dict structure.
        Supports both single-vector legacy format and multi-vector (5-photo) format.
        Returns: list of 128-D vector lists.
        """
        if not encoding:
            return []
        if isinstance(encoding, str):
            try:
                encoding = json.loads(encoding)
            except Exception:
                return []
        if isinstance(encoding, dict):
            if 'vectors' in encoding and isinstance(encoding['vectors'], list):
                return [v for v in encoding['vectors'] if isinstance(v, list) and len(v) == 128]
            if 'vector' in encoding and isinstance(encoding['vector'], list) and len(encoding['vector']) == 128:
                return [encoding['vector']]
            return []
        if isinstance(encoding, list):
            if len(encoding) > 0 and isinstance(encoding[0], list):
                return [v for v in encoding if isinstance(v, list) and len(v) == 128]
            elif len(encoding) == 128:
                return [encoding]
        return []

    def detect_faces_with_landmarks(self, image_np):
        """
        Detects faces using YuNet ONNX detector.
        Returns raw YuNet face objects containing bounding box and 5 facial landmarks.
        Format per face array: [x, y, w, h, x_re, y_re, x_le, y_le, x_nt, y_nt, x_rm, y_rm, x_lm, y_lm, score]
        """
        if image_np is None or image_np.size == 0:
            return []
        h, w = image_np.shape[:2]
        try:
            detector = self._get_detector(w, h)
            retval, faces = detector.detect(image_np)
            if retval > 0 and faces is not None and len(faces) > 0:
                return faces
        except Exception as e:
            pass
        return []

    def detect_faces(self, image_np):
        """
        Detects faces and returns list of (x, y, w, h) bounding boxes.
        Uses YuNet detector primarily, falling back to Haar Cascade.
        """
        raw_faces = self.detect_faces_with_landmarks(image_np)
        if len(raw_faces) > 0:
            boxes = []
            for face in raw_faces:
                x, y, w, h = int(face[0]), int(face[1]), int(face[2]), int(face[3])
                boxes.append((x, y, w, h))
            return boxes

        # Haar Cascade Fallback
        if image_np is None or image_np.size == 0:
            return []
        gray = cv2.cvtColor(image_np, cv2.COLOR_BGR2GRAY) if len(image_np.shape) == 3 else image_np
        gray = cv2.equalizeHist(gray)
        faces = self.face_cascade.detectMultiScale(
            gray,
            scaleFactor=1.1,
            minNeighbors=5,
            minSize=(60, 60),
            flags=cv2.CASCADE_SCALE_IMAGE
        )
        return [(int(x), int(y), int(w), int(h)) for (x, y, w, h) in faces]

    def extract_encoding(self, image_np, face_box=None):
        """
        Extracts 128-D SFace Deep Learning Face Embedding vector as a list of 128 floats.
        Uses landmark-aligned face crops for optimal accuracy.
        """
        if image_np is None or image_np.size == 0:
            return None

        h, w = image_np.shape[:2]

        try:
            # 1. Try raw YuNet detection with facial landmarks
            raw_faces = self.detect_faces_with_landmarks(image_np)
            selected_face = None

            if face_box is not None and len(raw_faces) > 0:
                bx, by, bw, bh = face_box
                best_overlap = -1
                for f in raw_faces:
                    fx, fy, fw, fh = f[0], f[1], f[2], f[3]
                    dx = min(bx + bw, fx + fw) - max(bx, fx)
                    dy = min(by + bh, fy + fh) - max(by, fy)
                    if dx > 0 and dy > 0:
                        overlap = dx * dy
                        if overlap > best_overlap:
                            best_overlap = overlap
                            selected_face = f
            elif len(raw_faces) > 0:
                selected_face = raw_faces[0]

            if selected_face is not None:
                aligned_face = self.recognizer.alignCrop(image_np, selected_face)
                feature = self.recognizer.feature(aligned_face)
                return [float(val) for val in feature.flatten()]

            # 2. If bounding box provided without landmarks (e.g., from Haar Cascade)
            if face_box is not None:
                bx, by, bw, bh = face_box
                pseudo_face = np.array([
                    bx, by, bw, bh,
                    bx + bw * 0.3, by + bh * 0.35,
                    bx + bw * 0.7, by + bh * 0.35,
                    bx + bw * 0.5, by + bh * 0.55,
                    bx + bw * 0.35, by + bh * 0.75,
                    bx + bw * 0.65, by + bh * 0.75,
                    1.0
                ], dtype=np.float32)
                aligned_face = self.recognizer.alignCrop(image_np, pseudo_face)
                feature = self.recognizer.feature(aligned_face)
                return [float(val) for val in feature.flatten()]

            # 3. Direct crop on whole image frame
            pseudo_face = np.array([
                0, 0, w, h,
                w * 0.3, h * 0.35,
                w * 0.7, h * 0.35,
                w * 0.5, h * 0.55,
                w * 0.35, h * 0.75,
                w * 0.65, h * 0.75,
                1.0
            ], dtype=np.float32)
            aligned_face = self.recognizer.alignCrop(image_np, pseudo_face)
            feature = self.recognizer.feature(aligned_face)
            return [float(val) for val in feature.flatten()]
        except Exception as e:
            print(f"Error extracting SFace encoding: {e}")
            return None

    def compute_similarity(self, encoding1, encoding2):
        """
        Computes Cosine Similarity (0.0 to 1.0) between two 128-D SFace feature vectors.
        """
        v1_list = self._parse_vector(encoding1)
        v2_list = self._parse_vector(encoding2)
        if not v1_list or not v2_list:
            return 0.0
        try:
            v1 = np.array(v1_list, dtype=np.float32).flatten()
            v2 = np.array(v2_list, dtype=np.float32).flatten()
        except Exception:
            return 0.0

        if v1.size != 128 or v2.size != 128:
            return 0.0

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
            (0, 230, 118),
            1,
            cv2.LINE_AA
        )
        return stamped_img

    def process_live_frame(self, image_np, student_records, session_id, undetected_folder):
        """
        Processes a live video frame:
        1. Detects all faces.
        2. Compares 128-D SFace encodings against ALL 5 registered embeddings of each student.
        3. Returns recognized students.
        4. Saves unrecognized / unknown faces into dataset/unknown_faces/<SESSION_ID>/ for teacher manual mapping.
        """
        stamped_img = self.add_anti_spoof_timestamp(image_np)
        raw_faces = self.detect_faces_with_landmarks(image_np)
        
        if len(raw_faces) == 0:
            haar_boxes = self.detect_faces(image_np)
            faces_to_process = [('box', box) for box in haar_boxes]
        else:
            faces_to_process = [('raw', f) for f in raw_faces]

        recognized_results = []
        undetected_saved = []

        h_img, w_img = image_np.shape[:2]
        assigned_student_ids = set()

        session_folder_name = f"session_{session_id}"
        session_unknown_dir = os.path.join(undetected_folder, session_folder_name)
        os.makedirs(session_unknown_dir, exist_ok=True)
        unknown_counter = len(os.listdir(session_unknown_dir)) + 1

        for face_type, face_data in faces_to_process:
            if face_type == 'raw':
                x, y, w, h = int(face_data[0]), int(face_data[1]), int(face_data[2]), int(face_data[3])
                encoding = self.extract_encoding(image_np, (x, y, w, h))
            else:
                x, y, w, h = face_data
                encoding = self.extract_encoding(image_np, (x, y, w, h))

            if not encoding:
                continue

            best_match_student = None
            highest_sim = 0.0

            for student in student_records:
                if not student.encoding_json:
                    continue
                if student.id in assigned_student_ids:
                    continue
                try:
                    s_vectors = self._parse_vectors(student.encoding_json)
                    if not s_vectors:
                        continue
                    for vec in s_vectors:
                        sim = self.compute_similarity(encoding, vec)
                        if sim > highest_sim:
                            highest_sim = sim
                            best_match_student = student
                except Exception:
                    continue

            if best_match_student and highest_sim >= self.match_threshold:
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
                cv2.rectangle(stamped_img, (x, y), (x + w, y + h), (0, 230, 118), 2)
                cv2.putText(stamped_img, f"{best_match_student.name} ({round(highest_sim*100)}%)", 
                            (x, max(y - 10, 20)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 230, 118), 2)
            else:
                # Unrecognized / Unknown face handling: Save crop under dataset/unknown_faces/<SESSION_ID>/
                pad_x, pad_y = int(w * 0.2), int(h * 0.2)
                crop_x1 = max(0, x - pad_x)
                crop_y1 = max(0, y - pad_y)
                crop_x2 = min(w_img, x + w + pad_x)
                crop_y2 = min(h_img, y + h + pad_y)
                
                face_crop = image_np[crop_y1:crop_y2, crop_x1:crop_x2]
                if face_crop is not None and face_crop.size > 0:
                    filename = f"unknown_{unknown_counter:03d}.jpg"
                    save_path = os.path.join(session_unknown_dir, filename)
                    cv2.imwrite(save_path, face_crop)
                    rel_path = f"dataset/unknown_faces/{session_folder_name}/{filename}"

                    import base64
                    _, crop_buffer = cv2.imencode('.jpg', face_crop)
                    crop_b64 = base64.b64encode(crop_buffer).decode('utf-8')

                    undetected_saved.append({
                        'image_path': rel_path,
                        'image_b64': crop_b64,
                        'bbox': [int(x), int(y), int(w), int(h)]
                    })
                    unknown_counter += 1

                cv2.rectangle(stamped_img, (x, y), (x + w, y + h), (255, 152, 0), 2)
                cv2.putText(stamped_img, "UNKNOWN FACE", (x, max(y - 10, 20)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 152, 0), 2)

        return stamped_img, recognized_results, undetected_saved

face_engine = FaceEngine(match_threshold=0.40)
