/**
 * ╔══════════════════════════════════════════════════════════════════╗
 * ║  CodeForge — App Core                                           ║
 * ║  Authentication, API client, routing, and toast notifications   ║
 * ╚══════════════════════════════════════════════════════════════════╝
 */

const API_BASE = window.location.origin;

// ─── State ─────────────────────────────────────────────────────────
const AppState = {
  token: localStorage.getItem('codeforge_token') || null,
  user: JSON.parse(localStorage.getItem('codeforge_user') || 'null'),
  currentRoom: null,
};


// ─── API Client ────────────────────────────────────────────────────
async function api(path, options = {}) {
  const headers = {
    'Content-Type': 'application/json',
    ...options.headers,
  };

  if (AppState.token) {
    headers['Authorization'] = `Bearer ${AppState.token}`;
  }

  const res = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    body: options.body ? JSON.stringify(options.body) : undefined,
  });

  if (res.status === 204) return null;

  const data = await res.json();

  if (!res.ok) {
    throw new Error(data.detail || `API Error: ${res.status}`);
  }

  return data;
}


// ─── Toast Notifications ───────────────────────────────────────────
function showToast(message, type = 'success', duration = 3000) {
  const container = document.getElementById('toastContainer');
  if (!container) return;

  const toast = document.createElement('div');
  toast.className = `toast glass toast-${type}`;
  toast.textContent = message;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.animation = 'pageExit 0.3s var(--ease-out) forwards';
    setTimeout(() => toast.remove(), 300);
  }, duration);
}


// ─── Auth Logic ────────────────────────────────────────────────────
function initAuth() {
  const loginForm = document.getElementById('loginForm');
  const registerForm = document.getElementById('registerForm');
  const showRegister = document.getElementById('showRegister');
  const showLogin = document.getElementById('showLogin');
  const authError = document.getElementById('authError');

  if (!loginForm) return; // Not on auth page

  // Toggle between login and register
  if (showRegister) {
    showRegister.addEventListener('click', () => {
      loginForm.classList.add('hidden');
      registerForm.classList.remove('hidden');
      if (authError) authError.classList.add('hidden');
    });
  }

  if (showLogin) {
    showLogin.addEventListener('click', () => {
      registerForm.classList.add('hidden');
      loginForm.classList.remove('hidden');
      if (authError) authError.classList.add('hidden');
    });
  }

  // Login
  loginForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('loginBtn');
    btn.innerHTML = '<div class="spinner"></div>';
    btn.disabled = true;

    try {
      const data = await api('/api/auth/login', {
        method: 'POST',
        body: {
          username: document.getElementById('loginUsername').value,
          password: document.getElementById('loginPassword').value,
        },
      });

      saveAuth(data);
      window.location.href = '/workspace';
    } catch (err) {
      showAuthError(err.message);
    } finally {
      btn.innerHTML = 'Sign In';
      btn.disabled = false;
    }
  });

  // Register
  registerForm.addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.getElementById('registerBtn');
    btn.innerHTML = '<div class="spinner"></div>';
    btn.disabled = true;

    try {
      const data = await api('/api/auth/register', {
        method: 'POST',
        body: {
          displayName: document.getElementById('regDisplayName').value,
          username: document.getElementById('regUsername').value,
          email: document.getElementById('regEmail').value,
          password: document.getElementById('regPassword').value,
        },
      });

      saveAuth(data);
      window.location.href = '/workspace';
    } catch (err) {
      showAuthError(err.message);
    } finally {
      btn.innerHTML = 'Create Account';
      btn.disabled = false;
    }
  });
}


function saveAuth(data) {
  AppState.token = data.token;
  AppState.user = data.user;
  localStorage.setItem('codeforge_token', data.token);
  localStorage.setItem('codeforge_user', JSON.stringify(data.user));
}


function showAuthError(message) {
  const el = document.getElementById('authError');
  if (el) {
    el.textContent = message;
    el.classList.remove('hidden');
  }
}


function logout() {
  AppState.token = null;
  AppState.user = null;
  localStorage.removeItem('codeforge_token');
  localStorage.removeItem('codeforge_user');
  window.location.href = '/';
}


function requireAuth() {
  if (!AppState.token || !AppState.user) {
    window.location.href = '/';
    return false;
  }
  return true;
}


// ─── Utility ───────────────────────────────────────────────────────
function getInitials(name) {
  return name
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);
}

function timeAgo(dateStr) {
  const diff = (Date.now() - new Date(dateStr).getTime()) / 1000;
  if (diff < 60) return 'just now';
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}


// ─── Initialize ────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  // Check if on auth page
  if (document.getElementById('authPage')) {
    // If already logged in, redirect to workspace
    if (AppState.token && AppState.user) {
      window.location.href = '/workspace';
      return;
    }
    initAuth();
  }
});
