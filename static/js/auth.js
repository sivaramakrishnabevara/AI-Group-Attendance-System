/* ==========================================================================
   AUTH MODULE
   Handles Login, JWT Tokens & Role Dashboard Switching
   ========================================================================== */

const getApiUrl = (path) => {
    const baseUrl = window.API_BASE_URL || '';
    if (!path.startsWith('/')) path = '/' + path;
    return baseUrl ? `${baseUrl}${path}` : path;
};

const auth = {
    token: localStorage.getItem('token'),
    user: null,

    async init() {
        if (this.token) {
            try {
                const res = await fetch(getApiUrl('/api/auth/me'), {
                    headers: { 'Authorization': `Bearer ${this.token}` }
                });
                const data = await res.json();
                if (data.success) {
                    this.user = data.user;
                    this.renderAuthenticatedUI();
                } else {
                    this.logout();
                }
            } catch (err) {
                this.logout();
            }
        } else {
            this.showLoginScreen();
        }
    },

    async handleLogin(e) {
        e.preventDefault();
        const username = document.getElementById('loginUsername').value;
        const password = document.getElementById('loginPassword').value;

        try {
            const res = await fetch(getApiUrl('/api/auth/login'), {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ username, password })
            });

            const data = await res.json();
            if (data.success) {
                this.token = data.token;
                this.user = data.user;
                localStorage.setItem('token', this.token);
                this.renderAuthenticatedUI();
            } else {
                alert(data.message || 'Login failed');
            }
        } catch (err) {
            alert('Error connecting to server. Please try again.');
        }
    },

    logout() {
        this.token = null;
        this.user = null;
        localStorage.removeItem('token');
        this.showLoginScreen();
    },

    showLoginScreen() {
        document.getElementById('loginScreen').style.display = 'block';
        document.getElementById('adminDashboard').style.display = 'none';
        document.getElementById('teacherDashboard').style.display = 'none';
        document.getElementById('userNav').style.display = 'none';
    },

    renderAuthenticatedUI() {
        document.getElementById('loginScreen').style.display = 'none';
        document.getElementById('userNav').style.display = 'flex';
        document.getElementById('userName').innerText = this.user.full_name;

        const rolePill = document.getElementById('rolePill');
        rolePill.innerText = this.user.role;
        rolePill.className = `role-pill ${this.user.role.toLowerCase()}`;

        if (this.user.role === 'ADMIN') {
            document.getElementById('adminDashboard').style.display = 'block';
            document.getElementById('teacherDashboard').style.display = 'none';
            admin.loadDashboardData();
        } else if (this.user.role === 'TEACHER') {
            document.getElementById('adminDashboard').style.display = 'none';
            document.getElementById('teacherDashboard').style.display = 'block';
            teacher.loadDashboardData();
        }
    }
};
