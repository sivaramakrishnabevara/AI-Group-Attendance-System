/* ==========================================================================
   WEBCAM MODULE
   Handles WebRTC Camera Stream & Face Capture for Student Registration
   ========================================================================== */

const webcam = {
    stream: null,
    capturedImageB64: null,

    openAddStudentModal() {
        document.getElementById('addStudentModal').classList.add('active');
        this.capturedImageB64 = null;
        const fileInput = document.getElementById('stPhotoFile');
        if (fileInput) fileInput.value = '';
        const previewContainer = document.getElementById('stPhotoPreviewContainer');
        if (previewContainer) previewContainer.style.display = 'none';
    },

    closeAddStudentModal() {
        document.getElementById('addStudentModal').classList.remove('active');
        this.capturedImageB64 = null;
        const form = document.getElementById('addStudentForm');
        if (form) form.reset();
        const previewContainer = document.getElementById('stPhotoPreviewContainer');
        if (previewContainer) previewContainer.style.display = 'none';
    },

    handlePhotoFileSelect(e) {
        const file = e.target.files[0];
        if (!file) return;

        const reader = new FileReader();
        reader.onload = (event) => {
            this.capturedImageB64 = event.target.result;
            const imgEl = document.getElementById('stPhotoPreviewImg');
            const containerEl = document.getElementById('stPhotoPreviewContainer');
            if (imgEl && containerEl) {
                imgEl.src = this.capturedImageB64;
                containerEl.style.display = 'block';
            }
        };
        reader.readAsDataURL(file);
    },

    async handleSaveStudent(e) {
        e.preventDefault();
        const name = document.getElementById('stName').value.trim();
        const roll_no = document.getElementById('stRollNo').value.trim();
        const class_name = document.getElementById('stClassName').value.trim();
        const parent_email = document.getElementById('stParentEmail').value.trim();

        try {
            const res = await fetch(getApiUrl('/api/students'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({
                    name,
                    roll_no,
                    class_name,
                    parent_email,
                    face_image: this.capturedImageB64
                })
            });

            const data = await res.json();
            if (data.success) {
                alert(data.message);
                this.closeAddStudentModal();
                if (auth.user.role === 'ADMIN') {
                    admin.loadStudents();
                } else if (auth.user.role === 'TEACHER') {
                    teacher.loadDashboardData();
                }
            } else {
                alert(data.message || 'Failed to register student');
            }
        } catch (err) {
            alert('Server error registering student.');
        }
    },

    // ---- Single Student Face Re-capture Camera Modal ----
    currentStudentIdToCapture: null,
    captureStream: null,
    singleCapturedImageB64: null,

    async openCaptureModalForStudent(studentId, studentName) {
        this.currentStudentIdToCapture = studentId;
        this.singleCapturedImageB64 = null;

        const nameEl = document.getElementById('captureModalStudentName');
        if (nameEl) nameEl.innerText = studentName || 'Student';

        const statusEl = document.getElementById('captureFaceModalStatus');
        if (statusEl) statusEl.innerText = 'Position student in front of camera, then click "Take Photo".';

        const snapBtn = document.getElementById('captureFaceSnapBtn');
        if (snapBtn) snapBtn.style.display = 'inline-flex';

        const resultPanel = document.getElementById('captureFaceResultPanel');
        if (resultPanel) resultPanel.style.display = 'none';

        const previewImg = document.getElementById('captureFacePreviewImg');
        if (previewImg) previewImg.style.display = 'none';

        const modal = document.getElementById('captureStudentFaceModal');
        if (modal) modal.classList.add('active');

        await this.startCaptureModalWebcam();
    },

    closeCaptureModalForStudent() {
        const modal = document.getElementById('captureStudentFaceModal');
        if (modal) modal.classList.remove('active');
        this.stopCaptureModalWebcam();
        this.currentStudentIdToCapture = null;
        this.singleCapturedImageB64 = null;
    },

    async startCaptureModalWebcam() {
        const statusEl = document.getElementById('captureFaceModalStatus');
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                const isIpAccess = window.location.protocol !== 'https:' && window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
                if (statusEl) {
                    statusEl.innerText = isIpAccess 
                        ? '⚠️ HTTP IP Blocks Camera! Open http://localhost:5000'
                        : '⚠️ Camera Blocked in Browser Settings';
                }
                return;
            }

            const video = document.getElementById('captureFaceVideo');
            this.captureStream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' }
            });
            video.srcObject = this.captureStream;
            if (statusEl) statusEl.innerText = 'Camera Ready — Click "Take Photo" below';
        } catch (err) {
            console.error("Camera access error:", err);
            if (statusEl) statusEl.innerText = '⚠️ Camera Access Denied. Check Browser Settings.';
        }
    },

    stopCaptureModalWebcam() {
        if (this.captureStream) {
            this.captureStream.getTracks().forEach(track => track.stop());
            this.captureStream = null;
        }
    },

    snapStudentFacePhoto() {
        const video = document.getElementById('captureFaceVideo');
        const canvas = document.getElementById('captureFaceCanvas');
        if (!video || !this.captureStream) return;

        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        this.singleCapturedImageB64 = canvas.toDataURL('image/jpeg');

        const previewImg = document.getElementById('captureFacePreviewImg');
        if (previewImg) {
            previewImg.src = this.singleCapturedImageB64;
            previewImg.style.display = 'block';
        }

        const snapBtn = document.getElementById('captureFaceSnapBtn');
        if (snapBtn) snapBtn.style.display = 'none';

        const resultPanel = document.getElementById('captureFaceResultPanel');
        if (resultPanel) resultPanel.style.display = 'block';

        const statusEl = document.getElementById('captureFaceModalStatus');
        if (statusEl) statusEl.innerText = '✅ Photo captured! Click "Save Face Photo" to update student dataset.';
    },

    retakeStudentFacePhoto() {
        this.singleCapturedImageB64 = null;

        const previewImg = document.getElementById('captureFacePreviewImg');
        if (previewImg) previewImg.style.display = 'none';

        const snapBtn = document.getElementById('captureFaceSnapBtn');
        if (snapBtn) snapBtn.style.display = 'inline-flex';

        const resultPanel = document.getElementById('captureFaceResultPanel');
        if (resultPanel) resultPanel.style.display = 'none';

        const statusEl = document.getElementById('captureFaceModalStatus');
        if (statusEl) statusEl.innerText = 'Camera Ready — Click "Take Photo" below';
    },

    async saveStudentFacePhoto() {
        if (!this.currentStudentIdToCapture || !this.singleCapturedImageB64) {
            alert('Please capture a photo first.');
            return;
        }

        const statusEl = document.getElementById('captureFaceModalStatus');
        if (statusEl) statusEl.innerText = '⏳ Extracting face vectors & saving image...';

        try {
            const res = await fetch(getApiUrl(`/api/students/${this.currentStudentIdToCapture}/face`), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({
                    face_image: this.singleCapturedImageB64
                })
            });

            const data = await res.json();
            if (data.success) {
                alert(data.message);
                this.closeCaptureModalForStudent();
                if (window.auth && auth.user && auth.user.role === 'ADMIN') {
                    admin.loadStudents();
                } else if (window.auth && auth.user && auth.user.role === 'TEACHER') {
                    teacher.loadStudentsDirectory();
                } else {
                    if (window.admin) admin.loadStudents();
                    if (window.teacher) teacher.loadStudentsDirectory();
                }
            } else {
                alert(data.message || 'Failed to save student face photo.');
                if (statusEl) statusEl.innerText = '⚠️ Error: ' + (data.message || 'Failed to save photo');
            }
        } catch (err) {
            console.error("Save face photo error:", err);
            alert('Server error saving face photo.');
            if (statusEl) statusEl.innerText = '⚠️ Server error saving face photo.';
        }
    }
};
