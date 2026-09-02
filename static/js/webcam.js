/* ==========================================================================
   WEBCAM MODULE
   Handles WebRTC Camera Stream & 5-Photo Face Capture Workflow for Student Registration
   ========================================================================== */

const webcam = {
    stream: null,
    capturedImages: [],
    studentData: {},
    isProcessingCapture: false,

    // ---- 5-Photo Student Registration Wizard ----
    openAddStudentWizard() {
        this.capturedImages = [];
        this.studentData = {};
        this.isProcessingCapture = false;
        
        // Reset form inputs
        const nameInput = document.getElementById('wizStName');
        const rollInput = document.getElementById('wizStRollNo');
        const classInput = document.getElementById('wizStClassName');
        const emailInput = document.getElementById('wizStParentEmail');

        if (nameInput) nameInput.value = '';
        if (rollInput) rollInput.value = '';
        if (classInput) classInput.value = 'Computer Science - Year 4';
        if (emailInput) emailInput.value = '';

        // Reset views
        const stepDetails = document.getElementById('regStepDetails');
        const stepCamera = document.getElementById('regStepCamera');
        const stepPreview = document.getElementById('regStepPreview');
        const stepComplete = document.getElementById('regStepComplete');

        if (stepDetails) stepDetails.style.display = 'block';
        if (stepCamera) stepCamera.style.display = 'none';
        if (stepPreview) stepPreview.style.display = 'none';
        if (stepComplete) stepComplete.style.display = 'none';

        this.updateStepIndicators(1);
        this.updateCaptureProgressUI();

        const modal = document.getElementById('addStudentWizardModal');
        if (modal) modal.classList.add('active');
    },

    closeAddStudentWizard() {
        const modal = document.getElementById('addStudentWizardModal');
        if (modal) modal.classList.remove('active');
        this.stopWizardCamera();
        this.capturedImages = [];
        this.studentData = {};
        this.isProcessingCapture = false;
    },

    updateStepIndicators(activeStep) {
        for (let i = 1; i <= 7; i++) {
            const el = document.getElementById(`stepIndicator${i}`);
            if (el) {
                if (i <= activeStep) {
                    el.style.color = 'var(--neon-cyan)';
                } else {
                    el.style.color = 'var(--text-muted)';
                }
            }
        }
    },

    updateCaptureProgressUI() {
        const count = this.capturedImages.length;
        const statusEl = document.getElementById('wizCameraStatus');
        const snapBtn = document.getElementById('wizSnapBtn');

        if (statusEl) {
            if (count === 0) {
                statusEl.innerText = 'Look directly at camera. Position face inside frame. (Photo 1 of 5)';
                statusEl.style.color = 'var(--neon-cyan)';
            } else if (count < 5) {
                statusEl.innerText = `Photo ${count} of 5 captured! Look at camera for photo ${count + 1} of 5.`;
                statusEl.style.color = 'var(--neon-emerald)';
            } else {
                statusEl.innerText = 'All 5 photos captured successfully!';
                statusEl.style.color = 'var(--neon-emerald)';
            }
        }

        if (snapBtn) {
            if (count < 5) {
                snapBtn.innerHTML = `<i class="fa-solid fa-camera"></i> 📸 Capture Photo ${count + 1} of 5`;
            } else {
                snapBtn.innerHTML = `<i class="fa-solid fa-check-double"></i> 5 Photos Captured — Proceeding to Preview...`;
            }
        }
    },

    async proceedToCameraStep() {
        const nameEl = document.getElementById('wizStName');
        const rollEl = document.getElementById('wizStRollNo');
        const classEl = document.getElementById('wizStClassName');
        const emailEl = document.getElementById('wizStParentEmail');

        if (!nameEl || !rollEl || !classEl || !emailEl) {
            alert('Registration modal form elements missing.');
            return;
        }

        const name = nameEl.value.trim();
        const roll_no = rollEl.value.trim();
        const class_name = classEl.value.trim();
        const parent_email = emailEl.value.trim();

        if (!name || !roll_no || !class_name || !parent_email) {
            alert('Please fill in all required fields (Name, Roll No, Class Name, and Parent Email Address).');
            return;
        }

        const emailPattern = /^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$/;
        if (!emailPattern.test(parent_email)) {
            alert('Please enter a valid Parent Email address (e.g., parent@example.com).');
            return;
        }

        this.studentData = { name, roll_no, class_name, parent_email };

        const stepDetails = document.getElementById('regStepDetails');
        const stepCamera = document.getElementById('regStepCamera');
        if (stepDetails) stepDetails.style.display = 'none';
        if (stepCamera) stepCamera.style.display = 'block';
        this.updateStepIndicators(3);

        await this.startWizardCamera();
    },

    async startWizardCamera() {
        const statusEl = document.getElementById('wizCameraStatus');
        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                if (statusEl) statusEl.innerText = '⚠️ Camera blocked by browser security settings or non-HTTPS connection.';
                alert('Webcam access requires HTTPS or localhost connection.');
                return;
            }

            const video = document.getElementById('wizCameraVideo');
            if (!video) return;

            this.stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' }
            });
            video.srcObject = this.stream;
            try {
                await video.play();
            } catch (e) {
                console.warn("Camera video play exception:", e);
            }
            this.updateCaptureProgressUI();
        } catch (err) {
            console.error("Wizard camera error:", err);
            if (statusEl) statusEl.innerText = '⚠️ Camera Access Denied. Please enable webcam permissions.';
            alert('Camera Access Denied or Unavailable. Please enable camera permissions in your browser.');
        }
    },

    stopWizardCamera() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
            this.stream = null;
        }
    },

    async snapWizardPhoto() {
        if (this.isProcessingCapture) return;
        if (this.capturedImages.length >= 5) {
            this.showPreviewStep();
            return;
        }

        const video = document.getElementById('wizCameraVideo');
        const canvas = document.getElementById('wizCameraCanvas');
        const statusEl = document.getElementById('wizCameraStatus');

        if (!video || !this.stream || !video.videoWidth) {
            alert('Camera stream is not active. Please ensure webcam permissions are enabled.');
            return;
        }

        this.isProcessingCapture = true;
        if (statusEl) statusEl.innerText = 'Analyzing face quality...';

        canvas.width = video.videoWidth || 640;
        canvas.height = video.videoHeight || 480;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const frameB64 = canvas.toDataURL('image/jpeg', 0.85);

        try {
            // Validate face count (must be exactly 1)
            const res = await safeApiFetch('/api/detect_face_check', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ image: frameB64 })
            });

            if (res.ok && res.data && res.data.success && res.data.count === 1) {
                this.capturedImages.push(frameB64);
                this.updateCaptureProgressUI();

                if (this.capturedImages.length >= 5) {
                    setTimeout(() => this.showPreviewStep(), 500);
                }
            } else if (res.data && res.data.count === 0) {
                alert('Face not detected. Please try again.');
                if (statusEl) statusEl.innerText = '❌ Face not detected. Please try again.';
            } else if (res.data && res.data.count > 1) {
                alert('Multiple faces detected. Only one student should be in the camera.');
                if (statusEl) statusEl.innerText = '❌ Multiple faces detected. Only one student should be in frame.';
            } else {
                alert(res.message || 'Face detection check failed.');
            }
        } catch (err) {
            console.error("Face capture validation error:", err);
            alert('Failed to connect to server for face detection check.');
        } finally {
            this.isProcessingCapture = false;
        }
    },

    showPreviewStep() {
        this.stopWizardCamera();

        // Populate student info
        document.getElementById('prevStudentName').innerText = this.studentData.name;
        document.getElementById('prevRollNo').innerText = this.studentData.roll_no;
        document.getElementById('prevClass').innerText = this.studentData.class_name;
        const emailEl = document.getElementById('prevEmail');
        if (emailEl) emailEl.innerText = this.studentData.parent_email;

        // Render 5 thumbnail previews
        const grid = document.getElementById('wizThumbnailsGrid');
        if (grid) {
            grid.innerHTML = '';
            this.capturedImages.forEach((imgB64, i) => {
                const item = document.createElement('div');
                item.style.textAlign = 'center';
                item.innerHTML = `
                    <img src="${imgB64}" style="width: 100%; height: 90px; object-fit: cover; border-radius: var(--radius-md); border: 2px solid var(--neon-cyan);" />
                    <div style="font-size: 0.75rem; color: var(--neon-cyan); margin-top: 0.2rem; font-weight: bold;">Photo #${i + 1}</div>
                `;
                grid.appendChild(item);
            });
        }

        document.getElementById('regStepCamera').style.display = 'none';
        document.getElementById('regStepPreview').style.display = 'block';
        this.updateStepIndicators(5);
    },

    async retakeWizardPhoto() {
        this.capturedImages = [];
        document.getElementById('regStepPreview').style.display = 'none';
        document.getElementById('regStepCamera').style.display = 'block';
        this.updateStepIndicators(3);
        await this.startWizardCamera();
    },

    async confirmAndRegisterStudent() {
        if (this.capturedImages.length < 5) {
            alert('EXACTLY 5 face images are required for registration. Please complete capture.');
            return;
        }

        this.updateStepIndicators(6);

        const res = await safeApiFetch('/api/students', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Authorization': `Bearer ${auth.token}`
            },
            body: JSON.stringify({
                name: this.studentData.name,
                roll_no: this.studentData.roll_no,
                class_name: this.studentData.class_name,
                parent_email: this.studentData.parent_email,
                face_images: this.capturedImages
            })
        });

        if (res.ok && res.data && res.data.success) {
            const stepPreview = document.getElementById('regStepPreview');
            const stepComplete = document.getElementById('regStepComplete');
            if (stepPreview) stepPreview.style.display = 'none';
            if (stepComplete) stepComplete.style.display = 'block';
            this.updateStepIndicators(7);

            if (window.admin && typeof admin.loadStudents === 'function') {
                admin.loadStudents();
            }
            if (window.teacher && typeof teacher.loadStudentsDirectory === 'function') {
                teacher.loadStudentsDirectory();
            }
        } else {
            alert(res.message || 'Failed to register student.');
        }
    }
};
