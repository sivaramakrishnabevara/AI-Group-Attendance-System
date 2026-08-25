/* ==========================================================================
   TEACHER MODULE
   Handles Live Attendance AI Loop & Export Reports
   ========================================================================== */

const teacher = {
    activeSessionId: null,
    liveInterval: null,
    isProcessingFrame: false,

    async loadDashboardData() {
        this.loadTeacherSessions();
        this.loadStudentsDirectory();
    },

    showTab(tabName) {
        const tabs = ['Attendance', 'Students', 'UnknownFaces', 'Reports'];
        tabs.forEach(t => {
            const btn = document.getElementById(`tabTeacherBtn${t}`);
            const content = document.getElementById(`teacherTab${t}`);
            if (btn && content) {
                if (t.toLowerCase() === tabName.toLowerCase()) {
                    btn.classList.add('active');
                    content.style.display = 'block';
                } else {
                    btn.classList.remove('active');
                    content.style.display = 'none';
                }
            }
        });
        if (tabName.toLowerCase() === 'students') {
            this.loadStudentsDirectory();
        } else if (tabName.toLowerCase() === 'unknownfaces') {
            this.loadUnknownFaces();
        } else if (tabName.toLowerCase() === 'reports') {
            this.loadTeacherSessions();
        }
    },

    async loadStudentsDirectory() {
        try {
            const res = await fetch(getApiUrl('/api/students'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                const tbody = document.getElementById('teacherStudentsTableBody');
                if (!tbody) return;
                tbody.innerHTML = '';
                if (!data.students || data.students.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No students registered yet. Click "Register Student with Face" to add.</td></tr>';
                    return;
                }
                data.students.forEach(st => {
                    const tr = document.createElement('tr');
                    const mobileNum = st.parent_mobile_number || st.parent_phone || 'N/A';
                    tr.innerHTML = `
                        <td><strong>${st.roll_no}</strong></td>
                        <td>${st.name}</td>
                        <td>${st.class_name}</td>
                        <td><code>${mobileNum}</code></td>
                        <td>
                            ${st.has_face 
                                ? '<span class="badge-status badge-present">✓ Encoded</span>' 
                                : '<span class="badge-status badge-absent">Missing Face</span>'}
                        </td>
                        <td style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                            <button onclick="webcam.openAddStudentWizard()" class="btn btn-primary btn-sm">
                                <i class="fa-solid fa-user-pen"></i> Register / Edit
                            </button>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } catch (err) {
            console.error("Error loading students:", err);
        }
    },

    async loadTeacherSessions() {
        try {
            const res = await fetch(getApiUrl('/api/sessions'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                this.renderSessionsTable(data.sessions);
            }
        } catch (err) {
            console.error("Failed to load sessions:", err);
        }
    },

    renderSessionsTable(sessions) {
        const tbody = document.getElementById('teacherSessionsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';
        
        if (!sessions || sessions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No attendance sessions found. Click "Start Attendance Camera" to begin.</td></tr>';
            return;
        }

        sessions.forEach(s => {
            const tr = document.createElement('tr');
            const statusClass = s.status === 'COMPLETED' ? 'badge-present' : 'badge-pending';
            tr.innerHTML = `
                <td><strong>${s.session_title}</strong></td>
                <td>${s.class_name}</td>
                <td>${s.created_at}</td>
                <td><span class="badge-status ${statusClass}">${s.status}</span></td>
                <td><strong>${s.present_count}</strong> / ${s.total_students}</td>
                <td>
                    <a href="/api/export/excel/${s.id}?token=${auth.token}" target="_blank" class="btn btn-emerald btn-sm" onclick="teacher.downloadReport(event, ${s.id}, 'excel')">
                        <i class="fa-solid fa-file-excel"></i> Excel
                    </a>
                    <a href="/api/export/pdf/${s.id}?token=${auth.token}" target="_blank" class="btn btn-purple btn-sm" onclick="teacher.downloadReport(event, ${s.id}, 'pdf')">
                        <i class="fa-solid fa-file-pdf"></i> PDF
                    </a>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    async downloadReport(e, sessionId, format) {
        e.preventDefault();
        try {
            const res = await fetch(getApiUrl(`/api/export/${format}/${sessionId}`), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            if (res.ok) {
                const blob = await res.blob();
                const url = window.URL.createObjectURL(blob);
                const a = document.createElement('a');
                a.href = url;
                a.download = `Attendance_Report_${sessionId}.${format === 'excel' ? 'xlsx' : 'pdf'}`;
                document.body.appendChild(a);
                a.click();
                a.remove();
            } else {
                alert("Error downloading report.");
            }
        } catch (err) {
            alert("Error connecting to server.");
        }
    },

    async startLiveSession() {
        const timeStr = new Date().toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'});
        const sessionTitle = `Lecture Attendance - ${timeStr}`;

        try {
            const res = await fetch(getApiUrl('/api/sessions/start'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({
                    session_title: sessionTitle,
                    class_name: 'Computer Science - Year 4'
                })
            });

            const data = await res.json();
            if (data.success) {
                this.activeSessionId = data.session.id;
                document.getElementById('activeSessionTitle').innerText = data.session.session_title;
                const panel = document.getElementById('liveAttendancePanel');
                panel.style.display = 'block';
                panel.scrollIntoView({ behavior: 'smooth' });
                await this.startWebcamFeed();
                this.updateLiveRecordsUI();
            } else {
                alert(data.message || 'Failed to start session');
            }
        } catch (err) {
            alert('Server error starting session.');
        }
    },

    async startWebcamFeed() {
        const video = document.getElementById('webcamVideo');
        const img = document.getElementById('processedStreamImg');
        if (img) img.style.display = 'none';
        if (video) video.style.display = 'block';

        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                alert('⚠️ Camera access error. Please grant webcam permissions in browser.');
                return;
            }

            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' }
            });
            video.srcObject = stream;
        } catch (err) {
            console.error("Webcam stream error:", err);
            alert(`⚠️ Camera access error: ${err.message || 'Permission denied'}`);
        }
    },

    resumeLiveVideoFeed() {
        const video = document.getElementById('webcamVideo');
        const img = document.getElementById('processedStreamImg');
        const resumeBtn = document.getElementById('resumeStreamBtn');
        if (img) img.style.display = 'none';
        if (video) video.style.display = 'block';
        if (resumeBtn) resumeBtn.style.display = 'none';
    },

    async triggerSnapDetection() {
        const flash = document.getElementById('cameraFlashOverlay');
        if (flash) {
            flash.classList.remove('flash-active');
            void flash.offsetWidth;
            flash.classList.add('flash-active');
        }

        await this.captureAndProcessFrame();
    },

    async captureAndProcessFrame() {
        if (this.isProcessingFrame || !this.activeSessionId) return;

        const video = document.getElementById('webcamVideo');
        const canvas = document.getElementById('webcamCanvas');
        if (!video || !video.videoWidth) return;

        this.isProcessingFrame = true;
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        const ctx = canvas.getContext('2d');
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

        const frameB64 = canvas.toDataURL('image/jpeg', 0.7);

        try {
            const res = await fetch(getApiUrl(`/api/sessions/${this.activeSessionId}/process_frame`), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ frame: frameB64 })
            });

            const data = await res.json();
            if (data.success) {
                const img = document.getElementById('processedStreamImg');
                img.src = data.processed_frame;
                img.style.display = 'block';
                video.style.display = 'none';

                const resumeBtn = document.getElementById('resumeStreamBtn');
                if (resumeBtn) resumeBtn.style.display = 'inline-flex';

                this.updateLiveRecordsUI();
                
                const metaLabel = document.getElementById('cameraStatusLabel');
                if (metaLabel) metaLabel.innerText = 'AI Detection Complete';
                const countLabel = document.getElementById('liveDetectedCount');
                if (countLabel) countLabel.innerText = data.recognized_count || 0;
            }
        } catch (err) {
            console.error("Frame processing error:", err);
        } finally {
            this.isProcessingFrame = false;
        }
    },

    async updateLiveRecordsUI() {
        if (!this.activeSessionId) return;
        try {
            const res = await fetch(getApiUrl(`/api/sessions/${this.activeSessionId}`), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                const list = document.getElementById('liveAttendanceList');
                if (!list) return;
                list.innerHTML = '';
                data.records.forEach(r => {
                    const li = document.createElement('li');
                    li.style.padding = '0.5rem 0';
                    li.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    li.style.display = 'flex';
                    li.style.justifyContent = 'space-between';
                    li.style.alignItems = 'center';

                    let badgeHtml = r.status === 'PRESENT'
                        ? '<span class="badge-status badge-present">✓ PRESENT</span>'
                        : '<span class="badge-status badge-absent">ABSENT</span>';

                    li.innerHTML = `
                        <span><strong>${r.student_name}</strong> (${r.roll_no})</span>
                        ${badgeHtml}
                    `;
                    list.appendChild(li);
                });
            }
        } catch (err) {
            console.error(err);
        }
    },

    async submitSessionForApproval() {
        if (!this.activeSessionId) return;

        try {
            const res = await fetch(getApiUrl(`/api/sessions/${this.activeSessionId}/submit_approval`), {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });

            const data = await res.json();
            if (data.success) {
                alert("Attendance session submitted for Admin approval! (Status: Submitted for Approval)");
            } else {
                alert(data.message || "Failed to submit session.");
            }
        } catch (err) {
            console.error("Error submitting session for approval:", err);
            alert("Error connecting to server.");
        } finally {
            document.getElementById('liveAttendancePanel').style.display = 'none';
            this.activeSessionId = null;
            this.loadTeacherSessions();
        }
    },

    async loadUnknownFaces() {
        const gallery = document.getElementById('teacherUnknownFacesGallery');
        if (!gallery) return;

        gallery.innerHTML = '<div style="color: var(--text-muted); font-size: 0.9rem;">Loading unknown faces...</div>';

        try {
            const url = this.activeSessionId 
                ? getApiUrl(`/api/unknown_faces?session_id=${this.activeSessionId}`)
                : getApiUrl('/api/unknown_faces');

            const [uRes, sRes] = await Promise.all([
                fetch(url, {
                    headers: { 'Authorization': `Bearer ${auth.token}` }
                }),
                fetch(getApiUrl('/api/students'), {
                    headers: { 'Authorization': `Bearer ${auth.token}` }
                })
            ]);

            const uData = await uRes.json();
            const sData = await sRes.json();

            const unknownFaces = uData.unknown_faces || uData.undetected_faces || [];
            const students = sData.students || [];

            gallery.innerHTML = '';
            if (unknownFaces.length === 0) {
                gallery.innerHTML = '<div style="color: var(--text-muted); font-size: 0.9rem; grid-column: 1/-1;">No unknown faces recorded for this session.</div>';
                return;
            }

            unknownFaces.forEach((uf, idx) => {
                const card = document.createElement('div');
                card.className = 'glass-card';
                card.style.padding = '0.85rem';
                card.style.background = 'rgba(15, 23, 42, 0.8)';

                let studentOptions = students.map(s => `<option value="${s.id}">${s.name} (${s.roll_no})</option>`).join('');
                let actionArea = '';

                if (uf.status === 'PENDING_ADMIN') {
                    actionArea = `<div style="font-size: 0.8rem; color: var(--neon-cyan); margin-top: 0.5rem; font-weight: bold;">Status: Pending Admin Approval</div>`;
                } else if (uf.status === 'APPROVED') {
                    actionArea = `<div style="font-size: 0.8rem; color: var(--neon-emerald); margin-top: 0.5rem; font-weight: bold;">✓ Approved by Admin</div>`;
                } else if (uf.status === 'REJECTED') {
                    actionArea = `<div style="font-size: 0.8rem; color: #ef4444; margin-top: 0.5rem; font-weight: bold;">✗ Rejected by Admin</div>`;
                } else {
                    actionArea = `
                        <select id="assignStudentSelect_${uf.id}" class="form-control" style="font-size: 0.8rem; padding: 0.35rem; margin-top: 0.5rem;">
                            <option value="">Select Student...</option>
                            ${studentOptions}
                        </select>
                        <button onclick="teacher.assignUnknownFace(${uf.id})" class="btn btn-primary btn-sm" style="width: 100%; margin-top: 0.5rem; font-size: 0.8rem;">
                            <i class="fa-solid fa-paper-plane"></i> Submit Assignment
                        </button>
                    `;
                }

                card.innerHTML = `
                    <div style="font-size: 0.8rem; font-weight: bold; color: var(--neon-cyan); margin-bottom: 0.4rem;">Unknown Face #U${String(uf.id).padStart(3, '0')}</div>
                    <img src="${getApiUrl('/' + uf.image_path.replace(/^\//, ''))}" style="width: 100%; height: 130px; object-fit: cover; border-radius: var(--radius-md); border: 1px solid var(--border-glass);" />
                    <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 0.3rem;">Time: ${uf.timestamp}</div>
                    ${actionArea}
                `;
                gallery.appendChild(card);
            });

        } catch (err) {
            console.error("Error loading unknown faces:", err);
            gallery.innerHTML = '<div style="color: #ef4444; font-size: 0.85rem;">Error loading unknown faces.</div>';
        }
    },

    async assignUnknownFace(undetectedId) {
        const select = document.getElementById(`assignStudentSelect_${undetectedId}`);
        if (!select || !select.value) {
            alert('Please select a student to assign this unknown face to.');
            return;
        }

        const student_id = parseInt(select.value);

        try {
            const res = await fetch(getApiUrl('/api/teacher/assign_unknown_face'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ undetected_id: undetectedId, student_id })
            });

            const data = await res.json();
            if (data.success) {
                alert("Assignment submitted! Status: Pending Admin Approval");
                this.loadUnknownFaces();
                this.updateLiveRecordsUI();
            } else {
                alert(data.message || "Failed to submit assignment.");
            }
        } catch (err) {
            console.error("Error assigning unknown face:", err);
            alert("Error connecting to server.");
        }
    },

    async stopLiveSession() {
        await this.submitSessionForApproval();
    }
};

