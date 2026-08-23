/* ==========================================================================
   TEACHER MODULE
   Handles Live Attendance AI Loop, Undetected Face Claiming & Exports
   ========================================================================== */

const teacher = {
    activeSessionId: null,
    liveInterval: null,
    isProcessingFrame: false,

    async loadDashboardData() {
        this.loadTeacherSessions();
        this.loadStudentsDirectory();
        this.loadUndetectedGallery();
    },

    showTab(tabName) {
        const tabs = ['Attendance', 'Students', 'Undetected', 'Reports', 'Email'];
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
        } else if (tabName.toLowerCase() === 'undetected') {
            this.loadUndetectedGallery();
        } else if (tabName.toLowerCase() === 'reports') {
            this.loadTeacherSessions();
        }
    },

    async loadStudentsDirectory() {
        try {
            const res = await fetch('/api/students', {
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
                    tr.innerHTML = `
                        <td><strong>${st.roll_no}</strong></td>
                        <td>${st.name}</td>
                        <td>${st.class_name}</td>
                        <td>${st.parent_email}</td>
                        <td>
                            ${st.has_face 
                                ? '<span class="badge-status badge-present">✓ Face Vector Active</span>' 
                                : '<span class="badge-status badge-absent">No Face Sample</span>'}
                        </td>
                        <td style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                            <button onclick="webcam.openCaptureModalForStudent(${st.id}, '${st.name.replace(/'/g, "\\'") }')" class="btn btn-primary btn-sm">
                                <i class="fa-solid fa-camera"></i> Photo
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
            const res = await fetch('/api/sessions', {
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
        tbody.innerHTML = '';
        
        if (!sessions || sessions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No attendance sessions found. Click "Start Live AI Attendance" to begin.</td></tr>';
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
            const res = await fetch(`/api/export/${format}/${sessionId}`, {
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
            const res = await fetch('/api/sessions/start', {
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
        img.style.display = 'none';
        video.style.display = 'block';

        try {
            if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
                const isIpAccess = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
                const msg = isIpAccess 
                    ? `⚠️ Camera access blocked by browser because you opened http://${window.location.hostname}:5000 over insecure HTTP.\n\n👉 FIX: Please open http://localhost:5000 on this computer, or allow camera permissions in Chrome settings!`
                    : `⚠️ Camera access error. Please ensure webcam permissions are granted in your browser settings.`;
                alert(msg);
                return;
            }

            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: 640, height: 480, facingMode: 'user' }
            });
            video.srcObject = stream;
        } catch (err) {
            console.error("Webcam stream error:", err);
            const isIpAccess = window.location.hostname !== 'localhost' && window.location.hostname !== '127.0.0.1';
            const msg = isIpAccess 
                ? `⚠️ Camera blocked on http://${window.location.hostname}:5000.\n\n👉 Solution 1: Open http://localhost:5000 in your browser.\n👉 Solution 2: Enable 'Insecure origins treated as secure' in chrome://flags.`
                : `⚠️ Camera access error: ${err.message || 'Permission denied'}. Please allow camera access in your browser site settings.`;
            alert(msg);
        }
    },

    resumeLiveVideoFeed() {
        const video = document.getElementById('webcamVideo');
        const img = document.getElementById('processedStreamImg');
        const resumeBtn = document.getElementById('resumeStreamBtn');
        if (img) img.style.display = 'none';
        if (video) video.style.display = 'block';
        if (resumeBtn) resumeBtn.style.display = 'none';
        
        const meta = document.getElementById('activeSessionMeta');
        if (meta) {
            meta.innerText = 'Position camera to view all students, then click "Snap Photo & Run AI Face Detection".';
        }
    },

    async triggerSnapDetection() {
        // Shutter flash effect animation
        const flash = document.getElementById('cameraFlashOverlay');
        if (flash) {
            flash.classList.remove('flash-active');
            void flash.offsetWidth; // Trigger reflow
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
            const res = await fetch(`/api/sessions/${this.activeSessionId}/process_frame`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ frame: frameB64 })
            });

            const data = await res.json();
            if (data.success) {
                // Show processed image with green/red bounding boxes & timestamp watermark
                const img = document.getElementById('processedStreamImg');
                img.src = data.processed_frame;
                img.style.display = 'block';
                video.style.display = 'none';

                const resumeBtn = document.getElementById('resumeStreamBtn');
                if (resumeBtn) resumeBtn.style.display = 'inline-flex';

                // Update real-time attendance list & snapshot storage confirmation
                this.updateLiveRecordsUI();
                
                const meta = document.getElementById('activeSessionMeta');
                if (meta) {
                    meta.innerHTML = `<span style="color:var(--neon-emerald); font-weight:bold;">✓ Photo Snapped & AI Face Detection Complete!</span><br><span style="color:var(--neon-cyan);">📸 Snapshot saved to: <code>${data.saved_snapshot_path}</code></span> (${data.recognized_count} recognized, ${data.undetected_count} unrecognized saved to <code>dataset/undetected_faces/</code>)`;
                }

                // If unrecognized faces were detected, automatically pop up the Unrecognized Faces Modal for teacher mapping
                if (data.undetected_count > 0) {
                    setTimeout(() => {
                        this.openUndetectedModal();
                    }, 600);
                }
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
            const res = await fetch(`/api/sessions/${this.activeSessionId}`, {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                const list = document.getElementById('liveAttendanceList');
                list.innerHTML = '';
                data.records.forEach(r => {
                    const li = document.createElement('li');
                    li.style.padding = '0.5rem 0';
                    li.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    li.style.display = 'flex';
                    li.style.justifyContent = 'space-between';
                    li.style.alignItems = 'center';

                    let badgeHtml = '';
                    if (r.approval_status === 'PENDING_ADMIN') {
                        badgeHtml = '<span class="badge-status badge-pending"><i class="fa-solid fa-clock"></i> Pending Admin Approval</span>';
                    } else if (r.status === 'PRESENT') {
                        badgeHtml = `<span class="badge-status badge-present">✓ PRESENT ${r.marking_method === 'MANUAL_TEACHER' ? '(Admin Approved)' : ''}</span>`;
                    } else {
                        badgeHtml = '<span class="badge-status badge-absent">ABSENT</span>';
                    }

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

    stopLiveSession() {
        if (this.liveInterval) clearInterval(this.liveInterval);
        document.getElementById('liveAttendancePanel').style.display = 'none';
        this.activeSessionId = null;
        this.loadTeacherSessions();
    },

    async openUndetectedModal() {
        if (!this.activeSessionId) {
            alert("Please start or select an active attendance session first.");
            return;
        }

        document.getElementById('undetectedModal').classList.add('active');
        await this.loadUndetectedGallery();
    },

    closeUndetectedModal() {
        document.getElementById('undetectedModal').classList.remove('active');
    },

    async proceedToFinalizeFromModal() {
        this.closeUndetectedModal();
        await this.finalizeSession();
    },

    async loadUndetectedGallery() {
        const gallery = document.getElementById('undetectedGallery');
        const tabGallery = document.getElementById('teacherUndetectedGallery');
        if (gallery) gallery.innerHTML = '<div style="color:var(--text-muted);">Loading unrecognized face snapshots...</div>';
        if (tabGallery) tabGallery.innerHTML = '<div style="color:var(--text-muted);">Loading unrecognized face snapshots...</div>';

        try {
            const url = this.activeSessionId ? `/api/undetected/${this.activeSessionId}` : '/api/undetected';
            const [uRes, stRes] = await Promise.all([
                fetch(url, { headers: { 'Authorization': `Bearer ${auth.token}` } }),
                fetch(`/api/students`, { headers: { 'Authorization': `Bearer ${auth.token}` } })
            ]);

            const uData = await uRes.json();
            const stData = await stRes.json();

            if (uData.success && stData.success) {
                const faces = uData.undetected_faces || uData.pending_approvals || [];
                const unclaimedCount = faces.filter(f => f.status === 'UNCLAIMED').length;
                const badgeEl = document.getElementById('teacherUndetectedBadge');
                if (badgeEl) badgeEl.innerText = unclaimedCount;

                if (gallery) gallery.innerHTML = '';
                if (tabGallery) tabGallery.innerHTML = '';

                if (faces.length === 0) {
                    const emptyMsg = '<div style="color:var(--text-muted); grid-column: 1/-1; text-align:center; padding: 2rem;">No unrecognized faces recorded.</div>';
                    if (gallery) gallery.innerHTML = emptyMsg;
                    if (tabGallery) tabGallery.innerHTML = emptyMsg;
                    return;
                }

                faces.forEach(uf => {
                    const card = document.createElement('div');
                    card.className = 'face-card';

                    let options = '<option value="">-- Select Student --</option>';
                    stData.students.forEach(s => {
                        options += `<option value="${s.id}">${s.name} (${s.roll_no})</option>`;
                    });

                    card.innerHTML = `
                        <img src="/${uf.image_path}" class="face-thumb" />
                        <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.4rem;">${uf.timestamp}</div>
                        <div style="font-size: 0.75rem; margin-bottom: 0.4rem;" class="badge-status ${uf.status === 'UNCLAIMED' ? 'badge-pending' : 'badge-present'}">
                            ${uf.status}
                        </div>
                        ${uf.status === 'UNCLAIMED' ? `
                            <select id="select_st_${uf.id}" class="form-control" style="font-size:0.8rem; margin-bottom: 0.5rem;">${options}</select>
                            <button onclick="teacher.submitManualClaim(${uf.id})" class="btn btn-purple btn-sm" style="width:100%;">
                                Submit Override
                            </button>
                        ` : `
                            <div style="font-size:0.75rem; color:var(--neon-cyan);">Claimed: ${uf.claimed_student_name || 'Mapped'}</div>
                        `}
                    `;
                    if (gallery) gallery.appendChild(card.cloneNode(true));
                    if (tabGallery) tabGallery.appendChild(card);
                });
            }
        } catch (err) {
            console.error(err);
        }
    },

    async submitManualClaim(undetectedId) {
        const select = document.getElementById(`select_st_${undetectedId}`);
        const studentId = select ? select.value : null;

        if (!studentId) {
            alert("Please select a student to match with this face.");
            return;
        }

        try {
            const res = await fetch('/api/undetected/claim', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({
                    undetected_id: undetectedId,
                    student_id: parseInt(studentId)
                })
            });

            const data = await res.json();
            if (data.success) {
                alert(data.message);
                this.loadUndetectedGallery();
                this.updateLiveRecordsUI();
            } else {
                alert(data.message || 'Failed to submit manual claim.');
            }
        } catch (err) {
            alert('Error submitting claim.');
        }
    },

    async openEmailSetupModal() {
        document.getElementById('emailSetupModal').classList.add('active');
        try {
            const res = await fetch('/api/admin/settings/email', {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                document.getElementById('modalSmtpEmail').value = data.settings.smtp_email || '';
                document.getElementById('modalEnableRealCheck').checked = data.settings.enable_real_email;
            }
        } catch (err) {
            console.error(err);
        }
    },

    closeEmailSetupModal() {
        document.getElementById('emailSetupModal').classList.remove('active');
    },

    async handleSaveEmailSetup(e) {
        e.preventDefault();
        const smtp_email = document.getElementById('modalSmtpEmail').value.trim();
        const smtp_password = document.getElementById('modalSmtpPassword').value.trim();
        const enable_real_email = document.getElementById('modalEnableRealCheck').checked;

        try {
            const res = await fetch('/api/admin/settings/email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ smtp_email, smtp_password, enable_real_email })
            });

            const data = await res.json();
            alert(data.message);
            if (data.success) this.closeEmailSetupModal();
        } catch (err) {
            alert('Error saving email settings.');
        }
    },

    async sendTestEmailFromModal() {
        const targetEmail = prompt("Enter email address to send test notice to:", document.getElementById('modalSmtpEmail').value || auth.user.email);
        if (!targetEmail) return;

        try {
            const res = await fetch('/api/admin/settings/test_email', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ target_email: targetEmail })
            });

            const data = await res.json();
            alert(data.message);
        } catch (err) {
            alert('Error sending test email.');
        }
    }
};
