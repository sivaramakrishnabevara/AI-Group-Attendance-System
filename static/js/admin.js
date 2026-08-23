/* ==========================================================================
   ADMIN MODULE
   Handles Faculty Management, Student Directory, Pending Manual Approvals
   ========================================================================== */

const admin = {
    loadDashboardData() {
        this.loadTeachers();
        this.loadStudents();
        this.loadPendingAttendance();
        this.loadAdminReports();
        this.loadEmailSettings();
    },

    showTab(tabName) {
        const tabs = ['Teachers', 'Students', 'Attendance', 'Reports', 'Email'];
        tabs.forEach(t => {
            const btn = document.getElementById(`tabBtn${t}`);
            const content = document.getElementById(`adminTab${t}`);
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

        if (tabName.toLowerCase() === 'attendance') {
            this.loadPendingAttendance();
        } else if (tabName.toLowerCase() === 'teachers') {
            this.loadTeachers();
        } else if (tabName.toLowerCase() === 'students') {
            this.loadStudents();
        } else if (tabName.toLowerCase() === 'reports') {
            this.loadAdminReports();
        } else if (tabName.toLowerCase() === 'email') {
            this.loadEmailSettings();
        }
    },

    async loadEmailSettings() {
        try {
            const res = await fetch('/api/admin/settings/email', {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                document.getElementById('smtpEmailInput').value = data.settings.smtp_email || '';
                document.getElementById('enableRealEmailCheck').checked = data.settings.enable_real_email;
            }
        } catch (err) {
            console.error("Error loading email settings:", err);
        }
    },

    async handleSaveEmailSettings(e) {
        e.preventDefault();
        const smtp_email = document.getElementById('smtpEmailInput').value.trim();
        const smtp_password = document.getElementById('smtpPasswordInput').value.trim();
        const enable_real_email = document.getElementById('enableRealEmailCheck').checked;

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
        } catch (err) {
            alert('Error saving email settings.');
        }
    },

    async sendTestEmail() {
        const targetEmail = prompt("Enter email address to send test notice to:", document.getElementById('smtpEmailInput').value || auth.user.email);
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
    },

    async loadTeachers() {
        try {
            const res = await fetch('/api/teachers', {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                document.getElementById('adminCountTeachers').innerText = data.teachers.length;
                this.renderTeachersTable(data.teachers);
            }
        } catch (err) {
            console.error("Error loading teachers:", err);
        }
    },

    renderTeachersTable(teachers) {
        const tbody = document.getElementById('teachersTableBody');
        tbody.innerHTML = '';

        if (!teachers || teachers.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No faculty teachers found. Click "Add New Teacher" to create one.</td></tr>';
            return;
        }

        teachers.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>#${t.id}</td>
                <td><strong>${t.full_name}</strong></td>
                <td><code>${t.username}</code></td>
                <td>${t.email}</td>
                <td><span class="role-pill teacher">TEACHER</span></td>
                <td style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <button onclick="admin.openEditTeacherModal(${t.id}, '${t.full_name.replace(/'/g, "\\'") }', '${t.username}', '${t.email}')" class="btn btn-outline btn-sm">
                        <i class="fa-solid fa-pen-to-square"></i> Edit
                    </button>
                    <button onclick="admin.deleteTeacher(${t.id})" class="btn btn-danger btn-sm">
                        <i class="fa-solid fa-trash"></i> Delete
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    openAddTeacherModal() {
        document.getElementById('addTeacherModal').classList.add('active');
    },

    closeAddTeacherModal() {
        document.getElementById('addTeacherModal').classList.remove('active');
    },

    // ---- Edit Teacher Modal ----
    openEditTeacherModal(id, fullName, username, email) {
        document.getElementById('editTeacherId').value = id;
        document.getElementById('editTFullName').value = fullName;
        document.getElementById('editTUsername').value = username;
        document.getElementById('editTEmail').value = email;
        document.getElementById('editTPassword').value = '';
        document.getElementById('editTeacherModal').classList.add('active');
    },

    closeEditTeacherModal() {
        document.getElementById('editTeacherModal').classList.remove('active');
    },

    async handleEditTeacher(e) {
        e.preventDefault();
        const id = document.getElementById('editTeacherId').value;
        const full_name = document.getElementById('editTFullName').value.trim();
        const username = document.getElementById('editTUsername').value.trim();
        const email = document.getElementById('editTEmail').value.trim();
        const password = document.getElementById('editTPassword').value.trim();

        try {
            const res = await fetch(`/api/teachers/${id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ full_name, username, email, password })
            });

            const data = await res.json();
            if (data.success) {
                alert(data.message);
                this.closeEditTeacherModal();
                this.loadTeachers();
            } else {
                alert(data.message || 'Failed to update teacher');
            }
        } catch (err) {
            alert('Error connecting to server.');
        }
    },

    async handleAddTeacher(e) {
        e.preventDefault();
        const full_name = document.getElementById('tFullName').value;
        const username = document.getElementById('tUsername').value;
        const email = document.getElementById('tEmail').value;
        const password = document.getElementById('tPassword').value;

        try {
            const res = await fetch('/api/teachers', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ full_name, username, email, password })
            });

            const data = await res.json();
            if (data.success) {
                alert(data.message);
                this.closeAddTeacherModal();
                this.loadTeachers();
            } else {
                alert(data.message || 'Failed to add teacher');
            }
        } catch (err) {
            alert('Error connecting to server.');
        }
    },

    async deleteTeacher(id) {
        if (!confirm("Are you sure you want to delete this teacher account?")) return;
        try {
            const res = await fetch(`/api/teachers/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                alert(data.message);
                this.loadTeachers();
            } else {
                alert(data.message);
            }
        } catch (err) {
            alert("Server error deleting teacher.");
        }
    },

    async loadStudents() {
        try {
            const res = await fetch('/api/students', {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                document.getElementById('adminCountStudents').innerText = data.students.length;
                this.renderStudentsTable(data.students);
            }
        } catch (err) {
            console.error("Error loading students:", err);
        }
    },

    renderStudentsTable(students) {
        const tbody = document.getElementById('studentsTableBody');
        tbody.innerHTML = '';

        if (!students || students.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No students registered yet. Click "Register Student with Face" to add.</td></tr>';
            return;
        }

        students.forEach(s => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${s.roll_no}</strong></td>
                <td>${s.name}</td>
                <td>${s.class_name}</td>
                <td>${s.parent_email}</td>
                <td>
                    <span class="badge-status ${s.has_face ? 'badge-present' : 'badge-absent'}">
                        ${s.has_face ? '✓ Encoded' : 'Missing Face'}
                    </span>
                </td>
                <td style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <button onclick="admin.openEditStudentModal(${s.id}, '${s.name.replace(/'/g, "\\'") }', '${s.roll_no}', '${s.class_name.replace(/'/g, "\\'") }', '${s.parent_email}')" class="btn btn-outline btn-sm">
                        <i class="fa-solid fa-pen-to-square"></i> Edit
                    </button>
                    <button onclick="webcam.openCaptureModalForStudent(${s.id}, '${s.name.replace(/'/g, "\\'") }')" class="btn btn-primary btn-sm">
                        <i class="fa-solid fa-camera"></i> Photo
                    </button>
                    <button onclick="admin.deleteStudent(${s.id})" class="btn btn-danger btn-sm">
                        <i class="fa-solid fa-trash"></i> Delete
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    // ---- Edit Student Modal ----
    openEditStudentModal(id, name, rollNo, className, parentEmail) {
        document.getElementById('editStudentId').value = id;
        document.getElementById('editStName').value = name;
        document.getElementById('editStRollNo').value = rollNo;
        document.getElementById('editStClassName').value = className;
        document.getElementById('editStParentEmail').value = parentEmail;
        document.getElementById('editStudentModal').classList.add('active');
    },

    closeEditStudentModal() {
        document.getElementById('editStudentModal').classList.remove('active');
    },

    async handleEditStudent(e) {
        e.preventDefault();
        const id = document.getElementById('editStudentId').value;
        const name = document.getElementById('editStName').value.trim();
        const roll_no = document.getElementById('editStRollNo').value.trim();
        const class_name = document.getElementById('editStClassName').value.trim();
        const parent_email = document.getElementById('editStParentEmail').value.trim();

        try {
            const res = await fetch(`/api/students/${id}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ name, roll_no, class_name, parent_email })
            });

            const data = await res.json();
            if (data.success) {
                alert(data.message);
                this.closeEditStudentModal();
                this.loadStudents();
            } else {
                alert(data.message || 'Failed to update student');
            }
        } catch (err) {
            alert('Error connecting to server.');
        }
    },

    async deleteStudent(id) {
        if (!confirm("Are you sure you want to delete this student record?")) return;
        try {
            const res = await fetch(`/api/students/${id}`, {
                method: 'DELETE',
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                alert(data.message);
                this.loadStudents();
            } else {
                alert(data.message);
            }
        } catch (err) {
            alert("Server error deleting student.");
        }
    },

    async loadPendingAttendance() {
        try {
            const res = await fetch('/api/sessions', {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                const pendingSessions = (data.sessions || []).filter(s => s.status !== 'COMPLETED' || s.pending_approval_count > 0);
                const count = pendingSessions.length;
                
                const cardEl = document.getElementById('adminCountPendingAttendance');
                if (cardEl) cardEl.innerText = count;
                const badgeEl = document.getElementById('pendingAttendanceBadge');
                if (badgeEl) badgeEl.innerText = count;

                this.renderPendingAttendanceTable(pendingSessions);
            }
        } catch (err) {
            console.error("Error loading pending attendance:", err);
        }
    },

    renderPendingAttendanceTable(sessions) {
        const tbody = document.getElementById('pendingAttendanceTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!sessions || sessions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted); padding:2rem;">No pending attendance sessions awaiting Admin finalization.</td></tr>';
            return;
        }

        sessions.forEach(s => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td><strong>${s.session_title}</strong></td>
                <td>${s.class_name}</td>
                <td>Prof. ${s.created_by_teacher_name}</td>
                <td>${s.created_at}</td>
                <td>
                    <span class="badge-status ${s.pending_approval_count > 0 ? 'badge-pending' : 'badge-present'}">
                        ${s.pending_approval_count > 0 ? `${s.pending_approval_count} Face Claims Pending` : 'Ready to Finalize'}
                    </span>
                </td>
                <td style="display:flex; gap:0.5rem; flex-wrap:wrap;">
                    ${s.pending_approval_count > 0 ? `
                        <button onclick="admin.viewSessionClaims(${s.id})" class="btn btn-purple btn-sm">
                            <i class="fa-solid fa-id-card-clip"></i> Verify Claims (${s.pending_approval_count})
                        </button>
                    ` : ''}
                    <button onclick="admin.finalizeSessionByAdmin(${s.id})" class="btn btn-emerald btn-sm btn-3d">
                        <i class="fa-solid fa-circle-check"></i> Finalize Attendance & Send Emails
                    </button>
                </td>
            `;
            tbody.appendChild(tr);
        });
    },

    async viewSessionClaims(sessionId) {
        this.activeClaimsSessionId = sessionId;
        document.getElementById('adminClaimsModal').classList.add('active');
        const gallery = document.getElementById('adminClaimsGallery');
        if (gallery) gallery.innerHTML = '<div style="color:var(--text-muted);">Loading teacher face claims...</div>';

        try {
            const res = await fetch(`/api/undetected/${sessionId}`, {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                gallery.innerHTML = '';
                const claimed = (data.undetected_faces || []).filter(f => f.claimed_student_name || f.status !== 'UNCLAIMED');
                if (claimed.length === 0) {
                    gallery.innerHTML = '<div style="color:var(--text-muted); grid-column: 1/-1; text-align:center; padding:1.5rem;">No manual face claims recorded for this session.</div>';
                    return;
                }

                claimed.forEach(uf => {
                    const card = document.createElement('div');
                    card.className = 'face-card';

                    let statusBadge = '';
                    if (uf.status === 'APPROVED') {
                        statusBadge = `<div style="margin-top:0.5rem; text-align:center;"><span class="badge-status badge-present">✓ Approved (PRESENT)</span></div>`;
                    } else if (uf.status === 'REJECTED') {
                        statusBadge = `<div style="margin-top:0.5rem; text-align:center;"><span class="badge-status badge-pending" style="background:rgba(239,68,68,0.2); color:#ef4444; border-color:rgba(239,68,68,0.4);">✗ Rejected (ABSENT)</span></div>`;
                    } else {
                        statusBadge = `
                            <div style="display:flex; gap:0.5rem; margin-top:0.5rem;">
                                <button onclick="admin.handleUndetectedClaimAction(${uf.id}, 'APPROVE')" class="btn btn-emerald btn-sm" style="flex:1;">
                                    <i class="fa-solid fa-check"></i> OK (Approve)
                                </button>
                                <button onclick="admin.handleUndetectedClaimAction(${uf.id}, 'REJECT')" class="btn btn-danger btn-sm" style="flex:1;">
                                    <i class="fa-solid fa-xmark"></i> Reject
                                </button>
                            </div>
                        `;
                    }

                    card.innerHTML = `
                        <img src="/${uf.image_path}" class="face-thumb" />
                        <div style="font-size: 0.8rem; font-weight: bold; margin-top: 0.3rem;">Mapped: ${uf.claimed_student_name || 'Student'}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.4rem;">Submitted by: ${uf.claimed_by_teacher_name || 'Teacher'}</div>
                        ${statusBadge}
                    `;
                    gallery.appendChild(card);
                });
            }
        } catch (err) {
            console.error("Error loading session face claims:", err);
        }
    },

    closeClaimsModal() {
        document.getElementById('adminClaimsModal').classList.remove('active');
        this.activeClaimsSessionId = null;
    },

    async handleUndetectedClaimAction(undetectedId, action) {
        try {
            const res = await fetch(`/api/admin/undetected/${undetectedId}/action`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ action })
            });
            const data = await res.json();
            if (data.success) {
                alert(data.message);
            } else {
                alert(data.message || "Error processing claim action.");
            }
            if (this.activeClaimsSessionId) {
                this.viewSessionClaims(this.activeClaimsSessionId);
            }
            this.loadPendingAttendance();
            this.loadAdminReports();
        } catch (err) {
            console.error("Error acting on claim:", err);
            alert("Error acting on claim.");
        }
    },

    async finalizeSessionFromClaimsModal() {
        if (this.activeClaimsSessionId) {
            const sessId = this.activeClaimsSessionId;
            this.closeClaimsModal();
            await this.finalizeSessionByAdmin(sessId);
        }
    },

    async handleApprovalAction(recordId, action) {
        try {
            const res = await fetch(`/api/admin/approvals/${recordId}/action`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ action })
            });

            const data = await res.json();
            if (data.success) {
                alert(data.message);
                this.loadPendingAttendance();
                this.loadAdminReports();
            } else {
                alert(data.message);
            }
        } catch (err) {
            alert("Error processing approval action.");
        }
    },

    async approveAllAndFinalize() {
        if (!confirm("Are you sure you want to approve all pending face claims and finalize attendance?")) return;

        try {
            const res = await fetch('/api/admin/approvals', {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            
            if (data.success && data.pending_approvals) {
                for (const app of data.pending_approvals) {
                    await fetch(`/api/admin/approvals/${app.id}/action`, {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json',
                            'Authorization': `Bearer ${auth.token}`
                        },
                        body: JSON.stringify({ action: 'APPROVE' })
                    });
                }
            }

            // Also check for active sessions to finalize
            const sRes = await fetch('/api/sessions', {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const sData = await sRes.json();
            if (sData.success && sData.sessions) {
                const activeSessions = sData.sessions.filter(s => s.status === 'ACTIVE');
                for (const sess of activeSessions) {
                    await fetch(`/api/sessions/${sess.id}/complete`, {
                        method: 'POST',
                        headers: { 'Authorization': `Bearer ${auth.token}` }
                    });
                }
            }

            alert("All pending attendance requests approved & session(s) finalized successfully!");
            this.loadPendingAttendance();
            this.loadAdminReports();
        } catch (err) {
            alert("Error approving and finalizing attendance.");
        }
    },

    async finalizeSessionByAdmin(sessionId) {
        if (!confirm("Finalize this session and dispatch automated parent absence emails?")) return;

        try {
            const res = await fetch(`/api/sessions/${sessionId}/complete`, {
                method: 'POST',
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });

            const data = await res.json();
            alert(data.message);
            this.loadPendingAttendance();
            this.loadAdminReports();
        } catch (err) {
            alert("Error finalizing session.");
        }
    },

    async loadAdminReports() {
        try {
            const res = await fetch('/api/sessions', {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                document.getElementById('adminCountSessions').innerText = data.sessions.length;
                this.renderAdminReportsTable(data.sessions);
            }
        } catch (err) {
            console.error("Error loading admin reports:", err);
        }
    },

    renderAdminReportsTable(sessions) {
        const tbody = document.getElementById('adminReportsTableBody');
        tbody.innerHTML = '';

        if (!sessions || sessions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No attendance records found.</td></tr>';
            return;
        }

        sessions.forEach(s => {
            const tr = document.createElement('tr');
            const isCompleted = s.status === 'COMPLETED';

            tr.innerHTML = `
                <td><strong>${s.session_title}</strong></td>
                <td>${s.class_name}</td>
                <td>Prof. ${s.created_by_teacher_name}</td>
                <td>${s.created_at}</td>
                <td><strong>${s.present_count}</strong> / ${s.total_students}</td>
                <td style="display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center;">
                    ${!isCompleted ? `
                        <button onclick="admin.finalizeSessionByAdmin(${s.id})" class="btn btn-emerald btn-sm">
                            <i class="fa-solid fa-circle-check"></i> Finalize Session
                        </button>
                    ` : `
                        <span class="badge-status badge-present">✓ COMPLETED</span>
                    `}
                    <a href="/api/export/excel/${s.id}?token=${auth.token}" target="_blank" class="btn btn-outline btn-sm" onclick="teacher.downloadReport(event, ${s.id}, 'excel')">
                        <i class="fa-solid fa-file-excel"></i> Excel
                    </a>
                    <a href="/api/export/pdf/${s.id}?token=${auth.token}" target="_blank" class="btn btn-outline btn-sm" onclick="teacher.downloadReport(event, ${s.id}, 'pdf')">
                        <i class="fa-solid fa-file-pdf"></i> PDF
                    </a>
                </td>
            `;
            tbody.appendChild(tr);
        });
    }
};
