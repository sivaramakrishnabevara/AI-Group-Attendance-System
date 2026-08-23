# AI Face Recognition Smart Attendance System
## Final Year Project - Requirements & Comprehensive Step-by-Step Guide

---

## 📋 1. Project Requirements & Tech Stack

### 🛠 Technology Stack
- **Language**: Python 3.11+
- **Backend Framework**: Flask REST API, Flask-CORS, Flask-SQLAlchemy
- **Computer Vision & AI**: OpenCV (`opencv-python`), NumPy, Pillow, Haar Cascade Face Detection, Cosine Embedding Matcher
- **Database**: SQLite3 with WAL (Write-Ahead Logging) mode
- **Email Dispatcher**: SMTP with TLS (Gmail App Password support)
- **Report Exporters**: `openpyxl` (Excel `.xlsx`), `reportlab` (PDF `.pdf`)
- **Frontend UI**: Modern Cyberpunk Glassmorphism SPA, Vanilla HTML5/CSS3/JavaScript, WebRTC Camera API

### 📦 Software Dependencies (`requirements.txt`)
```text
flask>=3.0.0
flask-cors>=4.0.0
flask-sqlalchemy>=3.1.1
opencv-python>=4.8.0
numpy>=1.24.0
Pillow>=10.0.0
openpyxl>=3.1.2
reportlab>=4.0.0
pyjwt>=2.8.0
werkzeug>=3.0.0
```

---

## ✅ 2. Completed Requirements Checklist (14 Instructions)

| # | Instruction / Requirement | Implementation Details |
|---|:---|:---|
| **1** | **2 Logins (Teacher & Admin)** | Secure role-based JWT authentication separating `ADMIN` and `TEACHER` accounts. |
| **2** | **Teacher Access** | Can register students with camera capture, conduct live AI face recognition sessions, and map undetected faces. |
| **3** | **Admin Access** | Full CRUD for Teachers and Students, pending manual attendance approval management, and report exports. |
| **4** | **Undetected Face Separate Folder** | Unrecognized person face crops during live attendance are automatically saved to `dataset/undetected_faces/`. |
| **5** | **Student Registration Face Storage** | WebRTC camera captures face snapshot -> feature vector extracted & saved in `dataset/students/`. |
| **6** | **Parent Absence Email Alert** | Finalizing session dispatches automated HTML emails with full student details to parents of all absent students. |
| **7** | **Anti-Spoofing Timestamp Verification** | Real-time millisecond server & client timestamp watermark is stamped onto live camera frames. |
| **8** | **One-Click AI Face Detection** | Clicking **"Snap Photo & Detect Faces Now"** activates real-time face detection, bounding box overlay, and saves snapshot to `dataset/session_snapshots/`. |
| **9** | **Teacher Manual Override** | Teachers open **Undetected Faces Gallery**, select unknown face crop, map to student, and submit override. |
| **10 & 11** | **Excel & PDF Export (Teacher + Admin)** | Download buttons on both dashboards generate formatted `.xlsx` and `.pdf` reports. |
| **12** | **Teacher Name Tracking** | Database logs `marked_by_teacher_name` whenever a manual attendance claim is submitted by a teacher. |
| **13** | **Admin Approval Workflow** | Manual overrides enter `PENDING_ADMIN` state. Admin reviews face thumbnail; clicking **OK (Approve)** marks `PRESENT`, while **Reject** marks `ABSENT`. |
| **14** | **Attractive Glowing UI** | High-contrast glassmorphism dark theme, ambient neon glows, camera flash shutter animation, and HUD viewfinder brackets. |

---

## 🚀 3. Step-by-Step Running Guide (Anaconda Prompt)

### Step 1: Open Anaconda Prompt
Open **Anaconda Prompt** from your Windows Start Menu.

### Step 2: Navigate to Project Directory
Type the following command and press Enter:
```cmd
cd "d:\Smart_Group_Attendance_System\ai attendence"
```

### Step 3: Install Required Packages (First Time Only)
Run the following command to install Python libraries:
```cmd
pip install -r requirements.txt
```

### Step 4: Launch the Server
Start the Flask application server:
```cmd
python app.py
```

### Step 5: Open Application in Web Browser
Open your browser (Chrome/Edge) and go to:
👉 **`http://localhost:5000`**

---

## 🔑 4. System Login Credentials

| Role | Username | Password | Key Privileges |
| :--- | :--- | :--- | :--- |
| **Administrator** | `admin` | `admin123` | Add/delete teachers, delete students, approve/reject manual face claims, export reports. |
| **Teacher** | `teacher` | `teacher123` | Register students with camera, take live attendance, snap photo for AI detection, claim undetected faces, export reports. |

---

## 📧 5. Parent Email Setup Guide (Gmail App Password)

1. Log in to the application at `http://localhost:5000`.
2. Click **`Configure Parent Email Alerts`** (on Teacher dashboard or Admin Email tab).
3. Enter your **Sender Gmail Address** (e.g. `yourname@gmail.com`).
4. Generate a 16-character **Gmail App Password**:
   - Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords).
   - Enter App Name (e.g., `Attendance System`) and click **Create**.
   - Copy the 16-character code (e.g., `abcd efgh ijkl mnop`).
5. Paste the 16-character password into **Gmail App Password**.
6. Check **`Enable Real Parent Email Delivery via Gmail SMTP`**.
7. Click **`Save & Enable Real Email`**, then click **`Send Test Email`**!
