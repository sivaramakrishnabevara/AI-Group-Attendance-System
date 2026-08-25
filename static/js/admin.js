/* ==========================================================================
   ADMIN MODULE
   Handles Faculty Management, Student Directory, Reports, SMS Settings
   ========================================================================== */

const admin = {
    loadDashboardData() {
        this.loadTeachers();
        this.loadStudents();
        this.loadAdminReports();
        this.loadSMSSettings();
    },

    showTab(tabName) {
        const tabs = ['Teachers', 'Students', 'UnknownFaces', 'Reports', 'Email'];
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

        if (tabName.toLowerCase() === 'teachers') {
            this.loadTeachers();
        } else if (tabName.toLowerCase() === 'students') {
            this.loadStudents();
        } else if (tabName.toLowerCase() === 'unknownfaces') {
            this.loadUnknownFaceApprovals();
        } else if (tabName.toLowerCase() === 'reports') {
            this.loadAdminReports();
        } else if (tabName.toLowerCase() === 'email') {
            this.loadEmailSettings();
            this.loadEmailLogs();
        }
    },

    unknownFacesCurrentPage: 1,
    unknownFacesPerPage: 10,
    unknownFacesData: [],

    async loadUnknownFaceApprovals() {
        const tbody = document.getElementById('adminUnknownFacesTableBody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color: var(--text-muted); padding: 2rem;"><i class="fa-solid fa-spinner fa-spin"></i> Loading unknown faces...</td></tr>';

        try {
            const res = await fetch(getApiUrl('/api/unknown_faces'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                this.unknownFacesData = data.unknown_faces || data.undetected_faces || [];
                this.unknownFacesCurrentPage = 1;
                this.renderUnknownFacesTable();
            } else {
                tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color: #ef4444; padding: 2rem;">Unable to load unknown faces.</td></tr>';
            }
        } catch (err) {
            console.error("Error loading unknown face approvals:", err);
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color: #ef4444; padding: 2rem;">Unable to load unknown faces.</td></tr>';
        }
    },

    renderUnknownFacesTable() {
        const tbody = document.getElementById('adminUnknownFacesTableBody');
        const paginationEl = document.getElementById('unknownFacesPagination');
        if (!tbody) return;
        tbody.innerHTML = '';

        const list = this.unknownFacesData || [];

        if (list.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="8" style="text-align:center; color: var(--text-muted); padding: 2.5rem 1rem;">
                        <i class="fa-solid fa-circle-check" style="font-size: 2rem; color: var(--neon-emerald); margin-bottom: 0.5rem; display: block;"></i>
                        No pending unknown faces.
                    </td>
                </tr>`;
            if (paginationEl) paginationEl.innerHTML = '';
            return;
        }

        const totalPages = Math.ceil(list.length / this.unknownFacesPerPage);
        if (this.unknownFacesCurrentPage < 1) this.unknownFacesCurrentPage = 1;
        if (this.unknownFacesCurrentPage > totalPages) this.unknownFacesCurrentPage = totalPages;

        const startIndex = (this.unknownFacesCurrentPage - 1) * this.unknownFacesPerPage;
        const pageItems = list.slice(startIndex, startIndex + this.unknownFacesPerPage);

        pageItems.forEach(uf => {
            const tr = document.createElement('tr');
            const status = uf.status || 'UNCLAIMED';

            let statusBadge = '';
            if (status === 'APPROVED') {
                statusBadge = '<span class="badge-status badge-present">APPROVED</span>';
            } else if (status === 'REJECTED') {
                statusBadge = '<span class="badge-status badge-absent">REJECTED</span>';
            } else if (status === 'PENDING_ADMIN') {
                statusBadge = '<span class="badge-status badge-pending" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4);">PENDING</span>';
            } else {
                statusBadge = `<span class="badge-status badge-pending">${status}</span>`;
            }

            const imgUrl = uf.image_path ? getApiUrl('/' + uf.image_path.replace(/^\//, '')) : '';
            const imgHtml = imgUrl ? `
                <img src="${imgUrl}" 
                     style="width: 44px; height: 44px; object-fit: cover; border-radius: var(--radius-md); border: 1px solid var(--border-glass);" 
                     onerror="this.onerror=null; this.outerHTML='<span style=\\'font-size:0.75rem; color:var(--text-muted);\\'>Image unavailable</span>';" />
            ` : '<span style="font-size:0.75rem; color:var(--text-muted);">Image unavailable</span>';

            const sessStr = uf.session_id ? `#S-${String(uf.session_id).padStart(3, '0')}` : 'N/A';
            const dateStr = uf.timestamp || 'N/A';
            const profStr = uf.claimed_by_teacher_name ? `Prof. ${uf.claimed_by_teacher_name}` : 'N/A';
            const studentStr = uf.claimed_student_name || 'Unassigned';

            let actionButtons = `
                <button onclick="admin.openUnknownFaceDetailModal(${uf.id})" class="btn btn-purple btn-sm" style="margin-right: 0.3rem;" title="Review details">
                    <i class="fa-solid fa-eye"></i> REVIEW
                </button>
            `;

            if (status !== 'APPROVED' && status !== 'REJECTED') {
                actionButtons += `
                    <button onclick="admin.handleUnknownFaceAction(${uf.id}, 'APPROVE')" class="btn btn-emerald btn-sm" style="margin-right: 0.3rem;">
                        <i class="fa-solid fa-check"></i> APPROVE
                    </button>
                    <button onclick="admin.handleUnknownFaceAction(${uf.id}, 'REJECT')" class="btn btn-danger btn-sm">
                        <i class="fa-solid fa-xmark"></i> REJECT
                    </button>
                `;
            }

            tr.innerHTML = `
                <td><strong>U${String(uf.id).padStart(3, '0')}</strong></td>
                <td>${imgHtml}</td>
                <td>${sessStr}</td>
                <td><span style="font-size:0.82rem; color:var(--text-muted);">${dateStr}</span></td>
                <td>${profStr}</td>
                <td><strong>${studentStr}</strong></td>
                <td>${statusBadge}</td>
                <td style="white-space: nowrap;">${actionButtons}</td>
            `;
            tbody.appendChild(tr);
        });

        if (paginationEl) {
            if (totalPages <= 1) {
                paginationEl.innerHTML = `<span style="font-size:0.85rem; color:var(--text-muted);">Showing all ${list.length} records</span>`;
            } else {
                let pageBtns = '';
                for (let i = 1; i <= totalPages; i++) {
                    const activeClass = i === this.unknownFacesCurrentPage ? 'btn-primary' : 'btn-outline';
                    pageBtns += `<button onclick="admin.changeUnknownFacesPage(${i})" class="btn ${activeClass} btn-sm" style="padding: 0.3rem 0.65rem; margin-right: 0.2rem;">${i}</button>`;
                }

                paginationEl.innerHTML = `
                    <div style="font-size:0.85rem; color:var(--text-muted);">
                        Showing ${startIndex + 1} to ${Math.min(startIndex + this.unknownFacesPerPage, list.length)} of ${list.length} records
                    </div>
                    <div style="display: flex; gap: 0.3rem; align-items: center;">
                        <button onclick="admin.changeUnknownFacesPage(${this.unknownFacesCurrentPage - 1})" 
                                class="btn btn-outline btn-sm" ${this.unknownFacesCurrentPage === 1 ? 'disabled' : ''}>
                            Previous
                        </button>
                        ${pageBtns}
                        <button onclick="admin.changeUnknownFacesPage(${this.unknownFacesCurrentPage + 1})" 
                                class="btn btn-outline btn-sm" ${this.unknownFacesCurrentPage === totalPages ? 'disabled' : ''}>
                            Next
                        </button>
                    </div>
                `;
            }
        }
    },

    changeUnknownFacesPage(page) {
        this.unknownFacesCurrentPage = page;
        this.renderUnknownFacesTable();
    },

    openUnknownFaceDetailModal(id) {
        const uf = (this.unknownFacesData || []).find(item => item.id === id);
        if (!uf) return;

        const modal = document.getElementById('adminUnknownFaceDetailModal');
        if (!modal) return;

        const imgUrl = uf.image_path ? getApiUrl('/' + uf.image_path.replace(/^\//, '')) : '';
        const imgEl = document.getElementById('ufDetailImage');
        if (imgEl) {
            if (imgUrl) {
                imgEl.src = imgUrl;
                imgEl.onerror = function() {
                    this.onerror = null;
                    this.style.display = 'none';
                    if (this.parentNode) this.parentNode.innerHTML = '<span style="font-size:0.75rem; color:var(--text-muted);">Image unavailable</span>';
                };
            } else {
                imgEl.style.display = 'none';
                if (imgEl.parentNode) imgEl.parentNode.innerHTML = '<span style="font-size:0.75rem; color:var(--text-muted);">Image unavailable</span>';
            }
        }

        const idEl = document.getElementById('ufDetailId');
        if (idEl) idEl.innerText = `U${String(uf.id).padStart(3, '0')}`;

        const sessEl = document.getElementById('ufDetailSession');
        if (sessEl) sessEl.innerText = uf.session_id ? `#S-${String(uf.session_id).padStart(3, '0')}` : 'N/A';

        const dateEl = document.getElementById('ufDetailDate');
        if (dateEl) dateEl.innerText = uf.timestamp || 'N/A';

        const profEl = document.getElementById('ufDetailProf');
        if (profEl) profEl.innerText = uf.claimed_by_teacher_name ? `Prof. ${uf.claimed_by_teacher_name}` : 'N/A';

        const studentEl = document.getElementById('ufDetailStudent');
        if (studentEl) studentEl.innerText = uf.claimed_student_name || 'Unassigned';

        const statusEl = document.getElementById('ufDetailStatus');
        if (statusEl) {
            statusEl.innerText = uf.status || 'UNCLAIMED';
            statusEl.className = `badge-status ${uf.status === 'APPROVED' ? 'badge-present' : uf.status === 'REJECTED' ? 'badge-absent' : 'badge-pending'}`;
        }

        const actionsEl = document.getElementById('ufDetailActions');
        if (actionsEl) {
            if (uf.status !== 'APPROVED' && uf.status !== 'REJECTED') {
                actionsEl.innerHTML = `
                    <button onclick="admin.handleUnknownFaceActionFromModal(${uf.id}, 'APPROVE')" class="btn btn-emerald btn-3d">
                        <i class="fa-solid fa-check"></i> APPROVE
                    </button>
                    <button onclick="admin.handleUnknownFaceActionFromModal(${uf.id}, 'REJECT')" class="btn btn-danger btn-3d">
                        <i class="fa-solid fa-xmark"></i> REJECT
                    </button>
                    <button onclick="admin.closeUnknownFaceDetailModal()" class="btn btn-outline">
                        CLOSE
                    </button>
                `;
            } else {
                actionsEl.innerHTML = `
                    <button onclick="admin.closeUnknownFaceDetailModal()" class="btn btn-outline">
                        CLOSE
                    </button>
                `;
            }
        }

        modal.classList.add('active');
    },

    closeUnknownFaceDetailModal() {
        const modal = document.getElementById('adminUnknownFaceDetailModal');
        if (modal) modal.classList.remove('active');
    },

    async handleUnknownFaceActionFromModal(id, action) {
        this.closeUnknownFaceDetailModal();
        await this.handleUnknownFaceAction(id, action);
    },

    async handleUnknownFaceAction(id, action) {
        try {
            const res = await fetch(getApiUrl(`/api/admin/unknown_faces/${id}/action`), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ action })
            });

            const data = await res.json();
            alert(data.message);
            this.loadUnknownFaceApprovals();
            this.loadAdminReports();
        } catch (err) {
            alert("Error acting on unknown face assignment.");
        }
    },

    toggleSMSFields() {
        const modeSelect = document.getElementById('smsModeSelect');
        const realGroup = document.getElementById('realSmsFieldsGroup');
        const badge = document.getElementById('smsModeBadgeDisplay');

        if (!modeSelect) return;
        const mode = modeSelect.value;

        if (mode === 'SIMULATION') {
            if (realGroup) realGroup.style.display = 'none';
            if (badge) {
                badge.innerText = 'SIMULATION (Free Project Mode)';
                badge.style.color = 'var(--neon-cyan)';
            }
        } else {
            if (realGroup) realGroup.style.display = 'block';
            if (badge) {
                badge.innerText = 'REAL_SMS (Paid Gateway Active)';
                badge.style.color = 'var(--neon-emerald)';
            }
        }
    },

    async loadSMSSettings() {
        try {
            const res = await fetch(getApiUrl('/api/admin/settings/sms'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success && data.settings) {
                const s = data.settings;
                const modeSelect = document.getElementById('smsModeSelect');
                if (modeSelect) modeSelect.value = s.sms_mode || 'SIMULATION';

                const providerSelect = document.getElementById('smsProviderSelect');
                if (providerSelect) providerSelect.value = s.sms_provider || 'FAST2SMS';

                const routeSelect = document.getElementById('smsRouteSelect');
                if (routeSelect) routeSelect.value = s.sms_route || 'q';

                const keyInput = document.getElementById('smsApiKeyInput');
                if (keyInput) keyInput.value = s.sms_api_key || '';

                const secretInput = document.getElementById('smsApiSecretInput');
                if (secretInput) secretInput.value = s.sms_api_secret || '';

                const senderInput = document.getElementById('smsSenderIdInput');
                if (senderInput) senderInput.value = s.sms_sender_id || 'ATTNDS';

                const dltInput = document.getElementById('smsDltTeIdInput');
                if (dltInput) dltInput.value = s.sms_dlt_te_id || '';

                const urlInput = document.getElementById('smsHttpUrlInput');
                if (urlInput) urlInput.value = s.sms_http_url || '';

                const check = document.getElementById('enableSMSCheck');
                if (check) check.checked = s.sms_enabled;

                this.toggleSMSFields();
            }
        } catch (err) {
            console.error("Error loading SMS settings:", err);
        }
        this.loadSMSLogs();
    },

    async loadSMSLogs() {
        const tbody = document.getElementById('adminSMSLogsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">Loading SMS history...</td></tr>';

        try {
            const res = await fetch(getApiUrl('/api/admin/sms_logs'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                tbody.innerHTML = '';
                const logs = data.logs || [];
                if (logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color: var(--text-muted);">No SMS notifications recorded yet. Finalize an attendance session to test.</td></tr>';
                    return;
                }

                logs.forEach(l => {
                    const tr = document.createElement('tr');
                    let statusBadge = '';
                    if (l.status === 'SIMULATED') {
                        statusBadge = '<span class="badge-status" style="background: rgba(0, 242, 254, 0.15); color: var(--neon-cyan); border: 1px solid rgba(0, 242, 254, 0.4);">SIMULATED</span>';
                    } else if (l.status === 'SENT') {
                        statusBadge = '<span class="badge-status badge-present">✓ SENT</span>';
                    } else {
                        statusBadge = '<span class="badge-status badge-absent">FAILED</span>';
                    }

                    let modeBadge = l.mode === 'SIMULATION'
                        ? '<span class="badge-status" style="background: rgba(176, 38, 255, 0.15); color: var(--neon-purple); border: 1px solid rgba(176, 38, 255, 0.4);">SIMULATION</span>'
                        : '<span class="badge-status badge-present">REAL_SMS</span>';

                    tr.innerHTML = `
                        <td><strong>${l.student_name}</strong></td>
                        <td>${l.roll_no}</td>
                        <td><code>${l.parent_mobile_masked}</code></td>
                        <td>${l.session_title}</td>
                        <td>${statusBadge}</td>
                        <td>${modeBadge}</td>
                        <td style="font-size: 0.8rem; max-width: 260px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${l.message}">${l.message}</td>
                        <td style="font-size: 0.8rem; color: var(--text-muted);">${l.timestamp}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } catch (err) {
            console.error("Error loading SMS logs:", err);
            tbody.innerHTML = '<tr><td colspan="8" style="text-align:center; color: #ef4444;">Error loading SMS history.</td></tr>';
        }
    },

    async handleSaveSMSSettings(e) {
        e.preventDefault();
        const sms_mode = document.getElementById('smsModeSelect').value;
        const sms_provider = document.getElementById('smsProviderSelect').value;
        const sms_route = document.getElementById('smsRouteSelect').value;
        const sms_api_key = document.getElementById('smsApiKeyInput').value.trim();
        const sms_api_secret = document.getElementById('smsApiSecretInput').value.trim();
        const sms_sender_id = document.getElementById('smsSenderIdInput').value.trim();
        const sms_dlt_te_id = document.getElementById('smsDltTeIdInput').value.trim();
        const sms_http_url = document.getElementById('smsHttpUrlInput').value.trim();
        const sms_enabled = document.getElementById('enableSMSCheck').checked;

        try {
            const res = await fetch(getApiUrl('/api/admin/settings/sms'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ sms_mode, sms_provider, sms_route, sms_api_key, sms_api_secret, sms_sender_id, sms_dlt_te_id, sms_http_url, sms_enabled })
            });

            const data = await res.json();
            alert(data.message);
            this.toggleSMSFields();
            this.loadSMSLogs();
        } catch (err) {
            alert('Error saving SMS settings.');
        }
    },

    openTestSMSModal() {
        const modal = document.getElementById('testSMSModal');
        if (modal) modal.classList.add('active');
    },

    closeTestSMSModal() {
        const modal = document.getElementById('testSMSModal');
        if (modal) modal.classList.remove('active');
    },

    async handleSendTestSMS(e) {
        e.preventDefault();
        const target_phone = document.getElementById('testSMSPhoneInput').value.trim();
        if (!target_phone) {
            alert('Please enter a target mobile number.');
            return;
        }

        try {
            const res = await fetch(getApiUrl('/api/admin/settings/test_sms'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ target_phone })
            });

            const data = await res.json();
            alert(data.message);
            if (data.success) {
                this.closeTestSMSModal();
                this.loadSMSLogs();
            }
        } catch (err) {
            alert('Error executing test SMS.');
        }
    },

    async loadTeachers() {
        try {
            const res = await fetch(getApiUrl('/api/teachers'), {
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
            tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No faculty professors found. Click "Add New Professor" to create one.</td></tr>';
            return;
        }

        teachers.forEach(t => {
            const tr = document.createElement('tr');
            tr.innerHTML = `
                <td>#${t.id}</td>
                <td><strong>${t.full_name}</strong></td>
                <td><code>${t.username}</code></td>
                <td>${t.email}</td>
                <td><span class="role-pill teacher">PROFESSOR</span></td>
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
            const res = await fetch(getApiUrl(`/api/teachers/${id}`), {
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
                alert(data.message || 'Failed to update professor');
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
            const res = await fetch(getApiUrl('/api/teachers'), {
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
                alert(data.message || 'Failed to add professor');
            }
        } catch (err) {
            alert('Error connecting to server.');
        }
    },

    async deleteTeacher(id) {
        if (!confirm("Are you sure you want to delete this professor account?")) return;
        try {
            const res = await fetch(getApiUrl(`/api/teachers/${id}`), {
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
            alert("Server error deleting professor.");
        }
    },

    async loadStudents() {
        try {
            const res = await fetch(getApiUrl('/api/students'), {
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
            const parentEmail = s.parent_email || `${s.roll_no ? s.roll_no.toLowerCase() : 'student'}@student.local`;
            tr.innerHTML = `
                <td><strong>${s.roll_no}</strong></td>
                <td>${s.name}</td>
                <td>${s.class_name}</td>
                <td><code>${parentEmail}</code></td>
                <td>
                    <span class="badge-status ${s.has_face ? 'badge-present' : 'badge-absent'}">
                        ${s.has_face ? '✓ Encoded' : 'Missing Face'}
                    </span>
                </td>
                <td style="display: flex; gap: 0.5rem; flex-wrap: wrap;">
                    <button onclick="admin.openEditStudentModal(${s.id}, '${s.name.replace(/'/g, "\\'")}', '${s.roll_no}', '${s.class_name.replace(/'/g, "\\'")}', '${parentEmail.replace(/'/g, "\\'")}')" class="btn btn-outline btn-sm">
                        <i class="fa-solid fa-pen-to-square"></i> Edit
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
        const emailEl = document.getElementById('editStParentEmail');
        if (emailEl) emailEl.value = parentEmail || '';
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
        const emailEl = document.getElementById('editStParentEmail');
        const parent_email = emailEl ? emailEl.value.trim() : '';

        try {
            const res = await fetch(getApiUrl(`/api/students/${id}`), {
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
            const res = await fetch(getApiUrl(`/api/students/${id}`), {
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
            const res = await fetch(getApiUrl('/api/sessions'), {
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
            const res = await fetch(getApiUrl(`/api/undetected/${sessionId}`), {
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
                        <img src="${getApiUrl(uf.image_path)}" class="face-thumb" />
                        <div style="font-size: 0.8rem; font-weight: bold; margin-top: 0.3rem;">Mapped: ${uf.claimed_student_name || 'Student'}</div>
                        <div style="font-size: 0.75rem; color: var(--text-muted); margin-bottom: 0.4rem;">Submitted by: ${uf.claimed_by_teacher_name || 'Professor'}</div>
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
            const res = await fetch(getApiUrl(`/api/admin/undetected/${undetectedId}/action`), {
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
            const res = await fetch(getApiUrl(`/api/admin/approvals/${recordId}/action`), {
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
            const res = await fetch(getApiUrl('/api/admin/approvals'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            
            if (data.success && data.pending_approvals) {
                for (const app of data.pending_approvals) {
                    await fetch(getApiUrl(`/api/admin/approvals/${app.id}/action`), {
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
            const sRes = await fetch(getApiUrl('/api/sessions'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const sData = await sRes.json();
            if (sData.success && sData.sessions) {
                const activeSessions = sData.sessions.filter(s => s.status === 'ACTIVE');
                for (const sess of activeSessions) {
                    await fetch(getApiUrl(`/api/sessions/${sess.id}/complete`), {
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
        if (!confirm("Are you sure you want to finalize this attendance session?\n\nThis will calculate final Present and Absent students, set session status to FINALIZED, and automatically send Gmail parent absence emails.")) return;

        try {
            const res = await fetch(getApiUrl(`/api/sessions/${sessionId}/finalize`), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                }
            });

            const data = await res.json();
            alert(data.message);
            this.loadPendingAttendance();
            this.loadAdminReports();
        } catch (err) {
            console.error("Error finalizing session:", err);
            alert("Error finalizing session.");
        }
    },

    async loadAdminReports() {
        console.log("[ADMIN REPORTS] Loading sessions...");
        const tbody = document.getElementById('adminReportsTableBody');
        if (tbody) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color: var(--text-muted); padding: 2rem;"><i class="fa-solid fa-spinner fa-spin"></i> Loading attendance sessions...</td></tr>';
        }
        try {
            const res = await fetch(getApiUrl('/api/sessions'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            console.log("[ADMIN REPORTS] API status:", res.status);
            const data = await res.json();
            console.log("[ADMIN REPORTS] Response:", data);

            const sessionsList = data ? (data.sessions || data.data || (Array.isArray(data) ? data : [])) : [];
            console.log("[ADMIN REPORTS] Session count:", sessionsList.length);

            const countEl = document.getElementById('adminCountSessions');
            if (countEl) countEl.innerText = sessionsList.length;

            console.log("[ADMIN REPORTS] Rendering table...");
            this.renderAdminReportsTable(sessionsList);
        } catch (err) {
            console.error("[ADMIN REPORTS] Error loading admin reports:", err);
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="10" style="text-align:center; color: #ef4444; padding: 2rem;">
                    Unable to load attendance sessions. 
                    <button onclick="admin.loadAdminReports()" class="btn btn-outline btn-sm" style="margin-left: 0.5rem;"><i class="fa-solid fa-rotate"></i> Retry</button>
                </td></tr>`;
            }
        }
    },

    renderAdminReportsTable(sessions) {
        const tbody = document.getElementById('adminReportsTableBody');
        if (!tbody) return;
        tbody.innerHTML = '';

        if (!sessions || sessions.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color: var(--text-muted); padding: 2rem;">No attendance sessions found.</td></tr>';
            return;
        }

        sessions.forEach(s => {
            if (!s) return;
            const tr = document.createElement('tr');
            const status = s.status || 'IN_PROGRESS';
            const isFinalized = status === 'FINALIZED';
            const isSubmitted = status === 'SUBMITTED_FOR_APPROVAL';

            let statusBadge = '';
            if (isFinalized) {
                statusBadge = '<span class="badge-status badge-present">FINALIZED</span>';
            } else if (isSubmitted) {
                statusBadge = '<span class="badge-status badge-pending" style="background: rgba(245, 158, 11, 0.2); color: #f59e0b; border: 1px solid rgba(245, 158, 11, 0.4);">PENDING APPROVAL</span>';
            } else {
                statusBadge = `<span class="badge-status badge-pending">${status}</span>`;
            }

            // Extract Date and Time from created_at string
            let dateStr = 'N/A';
            let timeStr = 'N/A';
            if (s.created_at) {
                const parts = String(s.created_at).split(' ');
                if (parts.length >= 1) dateStr = parts[0];
                if (parts.length >= 2) timeStr = parts.slice(1).join(' ');
            }

            const profName = s.created_by_teacher_name ? `Prof. ${s.created_by_teacher_name}` : 'N/A';
            const presentCount = s.present_count !== undefined ? s.present_count : 0;
            const absentCount = s.absent_count !== undefined ? s.absent_count : 0;
            const pendingCount = s.pending_approval_count !== undefined ? s.pending_approval_count : 0;
            const className = s.class_name || 'N/A';

            let actionsHtml = '';
            if (!isFinalized) {
                actionsHtml = `
                    <button onclick="admin.viewSessionClaims(${s.id})" class="btn btn-purple btn-sm" style="margin-right: 0.3rem;">
                        <i class="fa-solid fa-clipboard-check"></i> REVIEW ATTENDANCE
                    </button>
                    <button onclick="admin.finalizeSessionByAdmin(${s.id})" class="btn btn-emerald btn-sm btn-3d" style="margin-right: 0.3rem;">
                        <i class="fa-solid fa-circle-check"></i> FINALIZE ATTENDANCE
                    </button>
                    <a href="${getApiUrl('/api/export/excel/' + s.id)}?token=${auth.token}" target="_blank" class="btn btn-outline btn-sm" style="margin-right: 0.3rem;" title="Download Excel">
                        <i class="fa-solid fa-file-excel" style="color:var(--neon-emerald);"></i> Excel
                    </a>
                    <a href="${getApiUrl('/api/export/pdf/' + s.id)}?token=${auth.token}" target="_blank" class="btn btn-outline btn-sm" title="Download PDF">
                        <i class="fa-solid fa-file-pdf" style="color:#ef4444;"></i> PDF
                    </a>
                `;
            } else {
                actionsHtml = `
                    <span class="badge-status badge-present" style="margin-right: 0.3rem;">FINALIZED</span>
                    <button onclick="admin.viewSessionDetails(${s.id})" class="btn btn-purple btn-sm" style="margin-right: 0.3rem;">
                        <i class="fa-solid fa-eye"></i> VIEW DETAILS
                    </button>
                    <a href="${getApiUrl('/api/export/excel/' + s.id)}?token=${auth.token}" target="_blank" class="btn btn-outline btn-sm" style="margin-right: 0.3rem;" title="Download Excel">
                        <i class="fa-solid fa-file-excel" style="color:var(--neon-emerald);"></i> Excel
                    </a>
                    <a href="${getApiUrl('/api/export/pdf/' + s.id)}?token=${auth.token}" target="_blank" class="btn btn-outline btn-sm" title="Download PDF">
                        <i class="fa-solid fa-file-pdf" style="color:#ef4444;"></i> PDF
                    </a>
                `;
            }

            tr.innerHTML = `
                <td><strong>#S-${String(s.id || 0).padStart(3, '0')}</strong></td>
                <td>${dateStr}</td>
                <td>${timeStr}</td>
                <td>${profName}</td>
                <td>${className}</td>
                <td><span style="color:var(--neon-emerald); font-weight:bold;">${presentCount}</span></td>
                <td><span style="color:#ef4444; font-weight:bold;">${absentCount}</span></td>
                <td><span style="color:var(--neon-cyan); font-weight:bold;">${pendingCount}</span></td>
                <td>${statusBadge}</td>
                <td style="display: flex; gap: 0.4rem; flex-wrap: wrap; align-items: center;">${actionsHtml}</td>
            `;
            tbody.appendChild(tr);
        });
    },

    async viewSessionDetails(sessionId) {
        const modal = document.getElementById('sessionDetailsModal');
        if (modal) modal.classList.add('active');
        const headerEl = document.getElementById('sessionDetailsHeader');
        const tbody = document.getElementById('sessionDetailsTableBody');
        const exportsEl = document.getElementById('sessionDetailsExports');

        if (headerEl) headerEl.innerHTML = '<div style="color:var(--text-muted);"><i class="fa-solid fa-spinner fa-spin"></i> Loading session details...</div>';
        if (tbody) tbody.innerHTML = '';
        if (exportsEl) exportsEl.innerHTML = '';

        try {
            const res = await fetch(getApiUrl(`/api/sessions/${sessionId}`), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success && data.session) {
                const s = data.session;
                const records = data.records || [];

                if (headerEl) {
                    headerEl.innerHTML = `
                        <div style="font-size: 1.1rem; font-weight: bold; color: var(--neon-cyan); margin-bottom: 0.3rem;">
                            Session #S-${String(s.id).padStart(3, '0')}: ${s.session_title || s.class_name}
                        </div>
                        <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 0.5rem; font-size: 0.85rem; color: var(--text-muted); margin-top: 0.5rem;">
                            <div><strong>Session ID:</strong> #S-${String(s.id).padStart(3, '0')}</div>
                            <div><strong>Session Title:</strong> ${s.session_title || 'N/A'}</div>
                            <div><strong>Date & Time:</strong> ${s.created_at || 'N/A'}</div>
                            <div><strong>Professor:</strong> Prof. ${s.created_by_teacher_name || 'N/A'}</div>
                            <div><strong>Class:</strong> ${s.class_name || 'N/A'}</div>
                            <div><strong>Status:</strong> <span class="badge-status ${s.status === 'FINALIZED' ? 'badge-present' : 'badge-pending'}">${s.status}</span></div>
                        </div>
                        <div style="margin-top: 0.75rem; display: flex; gap: 1rem; font-size: 0.9rem;">
                            <span style="color: var(--neon-emerald); font-weight: bold;">Present: ${s.present_count || 0}</span>
                            <span style="color: #ef4444; font-weight: bold;">Absent: ${s.absent_count || 0}</span>
                            <span style="color: var(--neon-cyan); font-weight: bold;">Pending: ${s.pending_approval_count || 0}</span>
                        </div>
                    `;
                }

                if (tbody) {
                    if (records.length === 0) {
                        tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; color:var(--text-muted);">No student records found for this session.</td></tr>';
                    } else {
                        tbody.innerHTML = records.map(r => `
                            <tr>
                                <td><code>${r.roll_no || 'N/A'}</code></td>
                                <td><strong>${r.student_name || 'Unknown'}</strong></td>
                                <td>
                                    <span class="badge-status ${r.status === 'PRESENT' ? 'badge-present' : 'badge-absent'}">
                                        ${r.status}
                                    </span>
                                </td>
                                <td><span style="font-size: 0.8rem; color: var(--text-muted);">${r.marking_method || 'AI'}</span></td>
                                <td><span style="font-size: 0.8rem; color: var(--text-muted);">${r.timestamp || ''}</span></td>
                            </tr>
                        `).join('');
                    }
                }

                if (exportsEl) {
                    exportsEl.innerHTML = `
                        <a href="${getApiUrl('/api/export/excel/' + s.id)}?token=${auth.token}" target="_blank" class="btn btn-emerald btn-sm btn-3d">
                            <i class="fa-solid fa-file-excel"></i> DOWNLOAD EXCEL
                        </a>
                        <a href="${getApiUrl('/api/export/pdf/' + s.id)}?token=${auth.token}" target="_blank" class="btn btn-purple btn-sm btn-3d">
                            <i class="fa-solid fa-file-pdf"></i> DOWNLOAD PDF
                        </a>
                    `;
                }
            } else {
                if (headerEl) headerEl.innerHTML = '<div style="color:#ef4444;">Failed to load session details.</div>';
            }
        } catch (err) {
            console.error("Error loading session details:", err);
            if (headerEl) headerEl.innerHTML = '<div style="color:#ef4444;">Error connecting to server.</div>';
        }
    },

    closeSessionDetailsModal() {
        const modal = document.getElementById('sessionDetailsModal');
        if (modal) modal.classList.remove('active');
    },

    async loadEmailSettings() {
        try {
            const res = await fetch(getApiUrl('/api/admin/settings/email'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success && data.settings) {
                const s = data.settings;
                const emailInput = document.getElementById('gmailEmailInput');
                const passInput = document.getElementById('gmailAppPasswordInput');
                const enableCheck = document.getElementById('enableEmailCheck');

                if (emailInput) emailInput.value = s.gmail_email || '';
                if (passInput) passInput.value = s.gmail_app_password_masked || s.gmail_app_password || '';
                if (enableCheck) enableCheck.checked = s.enable_email_alerts !== false;
            }
        } catch (err) {
            console.error("Error loading Email settings:", err);
        }
    },

    async handleSaveEmailSettings(e) {
        if (e) e.preventDefault();
        const gmail_email = document.getElementById('gmailEmailInput').value.trim();
        const gmail_app_password = document.getElementById('gmailAppPasswordInput').value.trim();
        const enable_email_alerts = document.getElementById('enableEmailCheck').checked;

        try {
            const res = await fetch(getApiUrl('/api/admin/settings/email'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({
                    enable_email_alerts,
                    gmail_email,
                    gmail_app_password
                })
            });

            const data = await res.json();
            alert(data.message);
            if (data.success) {
                this.loadEmailSettings();
            }
        } catch (err) {
            alert("Failed to save Email settings.");
        }
    },

    async loadEmailLogs() {
        const tbody = document.getElementById('adminEmailLogsTableBody');
        if (!tbody) return;

        try {
            const res = await fetch(getApiUrl('/api/admin/email_logs'), {
                headers: { 'Authorization': `Bearer ${auth.token}` }
            });
            const data = await res.json();
            if (data.success) {
                tbody.innerHTML = '';
                const logs = data.logs || [];
                if (logs.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="6" style="text-align:center; color: var(--text-muted);">No parent email notification records found.</td></tr>';
                    return;
                }

                logs.forEach(l => {
                    const tr = document.createElement('tr');
                    const isSuccess = l.status === 'SENT' || l.status === 'SIMULATED';
                    const badgeClass = isSuccess ? 'badge-present' : 'badge-absent';

                    tr.innerHTML = `
                        <td><strong>${l.student_name}</strong></td>
                        <td>${l.roll_no}</td>
                        <td><code>${l.parent_email_masked || l.parent_email}</code></td>
                        <td><span style="color: var(--neon-cyan);">${l.session_title}</span> — ${l.subject}</td>
                        <td><span class="badge-status ${badgeClass}">${l.status}</span></td>
                        <td style="font-size: 0.82rem; color: var(--text-muted);">${l.timestamp}</td>
                    `;
                    tbody.appendChild(tr);
                });
            }
        } catch (err) {
            console.error("Error loading email logs:", err);
        }
    },

    openTestEmailModal() {
        const modal = document.getElementById('testEmailModal');
        if (modal) modal.classList.add('active');
    },

    closeTestEmailModal() {
        const modal = document.getElementById('testEmailModal');
        if (modal) modal.classList.remove('active');
    },

    async handleSendTestEmail(e) {
        if (e) e.preventDefault();
        const targetEmail = document.getElementById('testEmailTargetInput').value.trim();
        if (!targetEmail) {
            alert('Please enter a target email address.');
            return;
        }

        try {
            const res = await fetch(getApiUrl('/api/admin/settings/test_email'), {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${auth.token}`
                },
                body: JSON.stringify({ email: targetEmail })
            });
            const data = await res.json();
            alert(data.message);
            if (data.success) {
                this.closeTestEmailModal();
                this.loadEmailLogs();
            }
        } catch (err) {
            alert("Error sending test email.");
        }
    }
};
