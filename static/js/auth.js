/* ==========================================================================
   AUTH MODULE
   Handles Login, JWT Tokens & Role Dashboard Switching
   ========================================================================== */

const getApiUrl = (path) => {
    let baseUrl = (window.API_BASE_URL || '').trim();
    if (baseUrl.endsWith('/')) baseUrl = baseUrl.slice(0, -1);
    if (!path.startsWith('/')) path = '/' + path;
    return baseUrl ? `${baseUrl}${path}` : path;
};

const safeApiFetch = async (path, options = {}) => {
    const url = getApiUrl(path);
    const method = (options.method || 'GET').toUpperCase();
    
    // Diagnostic logging before request (omitting secrets)
    console.log(`[API REQUEST] ${method} ${url}`);

    try {
        const res = await fetch(url, options);
        const contentType = res.headers.get('content-type') || '';
        
        console.log(`[API RESPONSE] ${method} ${url} -> Status: ${res.status} ${res.statusText} (${contentType})`);

        if (!res.ok) {
            let errorMsg = `Server returned status ${res.status} (${res.statusText})`;
            if (contentType.includes('application/json')) {
                const errData = await res.json().catch(() => ({}));
                if (errData.message) errorMsg = errData.message;
            } else {
                const textBody = await res.text().catch(() => '');
                console.warn(`[API HTML/NON-JSON ERROR BODY] ${method} ${url} ->`, textBody.substring(0, 200));
            }
            console.error(`[API FAIL] ${method} ${url} -> ${errorMsg}`);
            return {
                ok: false,
                status: res.status,
                contentType,
                data: null,
                message: errorMsg
            };
        }

        if (contentType.includes('application/json')) {
            const data = await res.json();
            return {
                ok: true,
                status: res.status,
                contentType,
                data,
                message: data.message || 'Success'
            };
        } else {
            return {
                ok: true,
                status: res.status,
                contentType,
                response: res
            };
        }
    } catch (err) {
        console.error(`[API NETWORK ERROR] ${method} ${url} ->`, err.message);
        return {
            ok: false,
            status: 0,
            contentType: '',
            data: null,
            message: `Network error: ${err.message}. Please check connection.`
        };
    }
};

const auth = {
    token: localStorage.getItem('token'),
    user: null,

    async init() {
        if (this.token) {
            const res = await safeApiFetch('/api/auth/me', {
                headers: { 'Authorization': `Bearer ${this.token}` }
            });
            if (res.ok && res.data && res.data.success) {
                this.user = res.data.user;
                this.renderAuthenticatedUI();
            } else {
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

        const res = await safeApiFetch('/api/auth/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username, password })
        });

        if (res.ok && res.data && res.data.success) {
            this.token = res.data.token;
            this.user = res.data.user;
            localStorage.setItem('token', this.token);
            this.renderAuthenticatedUI();
        } else {
            alert(res.message || 'Login failed');
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
        rolePill.innerText = (this.user.role === 'TEACHER') ? 'PROFESSOR' : this.user.role;
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
