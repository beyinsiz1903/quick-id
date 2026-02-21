const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

function getToken() {
  return localStorage.getItem('quickid_token');
}

function authHeaders() {
  const token = getToken();
  return token ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
}

async function handleResponse(res) {
  if (res.status === 401) {
    localStorage.removeItem('quickid_token');
    localStorage.removeItem('quickid_user');
    window.location.href = '/login';
    throw new Error('Oturum süresi doldu');
  }
  if (res.status === 429) {
    throw new Error('İstek limiti aşıldı. Lütfen biraz bekleyin ve tekrar deneyin.');
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: 'İşlem başarısız' }));
    throw new Error(err.detail || 'İşlem başarısız');
  }
  return res.json();
}

export const api = {
  // Auth
  async login(email, password) {
    const res = await fetch(`${BACKEND_URL}/api/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ email, password }),
    });
    return handleResponse(res);
  },

  async getMe() {
    const res = await fetch(`${BACKEND_URL}/api/auth/me`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async changePassword(data) {
    const res = await fetch(`${BACKEND_URL}/api/auth/change-password`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  // Users (admin)
  async getUsers() {
    const res = await fetch(`${BACKEND_URL}/api/users`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async createUser(data) {
    const res = await fetch(`${BACKEND_URL}/api/users`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  async updateUser(id, data) {
    const res = await fetch(`${BACKEND_URL}/api/users/${id}`, {
      method: 'PATCH', headers: authHeaders(), body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  async deleteUser(id) {
    const res = await fetch(`${BACKEND_URL}/api/users/${id}`, { method: 'DELETE', headers: authHeaders() });
    return handleResponse(res);
  },

  async resetUserPassword(id, newPassword) {
    const res = await fetch(`${BACKEND_URL}/api/users/${id}/reset-password`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify({ new_password: newPassword }),
    });
    return handleResponse(res);
  },

  // KVKK Settings
  async getKvkkSettings() {
    const res = await fetch(`${BACKEND_URL}/api/settings/kvkk`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async updateKvkkSettings(data) {
    const res = await fetch(`${BACKEND_URL}/api/settings/kvkk`, {
      method: 'PATCH', headers: authHeaders(), body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  async triggerCleanup() {
    const res = await fetch(`${BACKEND_URL}/api/settings/cleanup`, { method: 'POST', headers: authHeaders() });
    return handleResponse(res);
  },

  async anonymizeGuest(id) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}/anonymize`, { method: 'POST', headers: authHeaders() });
    return handleResponse(res);
  },

  // Scan
  async scanId(imageBase64) {
    const res = await fetch(`${BACKEND_URL}/api/scan`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify({ image_base64: imageBase64 }),
    });
    return handleResponse(res);
  },

  async getScans(page = 1, limit = 20) {
    const res = await fetch(`${BACKEND_URL}/api/scans?page=${page}&limit=${limit}`, { headers: authHeaders() });
    return handleResponse(res);
  },

  // Duplicate check
  async checkDuplicate(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, v); });
    const res = await fetch(`${BACKEND_URL}/api/guests/check-duplicate?${query.toString()}`, { headers: authHeaders() });
    return handleResponse(res);
  },

  // Guests
  async createGuest(data) {
    const res = await fetch(`${BACKEND_URL}/api/guests`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  async getGuests(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v !== null && v !== undefined && v !== '') query.set(k, v); });
    const res = await fetch(`${BACKEND_URL}/api/guests?${query.toString()}`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async getGuest(id) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async updateGuest(id, data) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}`, {
      method: 'PATCH', headers: authHeaders(), body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  async deleteGuest(id) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}`, { method: 'DELETE', headers: authHeaders() });
    return handleResponse(res);
  },

  async checkinGuest(id) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}/checkin`, { method: 'POST', headers: authHeaders() });
    return handleResponse(res);
  },

  async checkoutGuest(id) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}/checkout`, { method: 'POST', headers: authHeaders() });
    return handleResponse(res);
  },

  // Audit Trail
  async getGuestAudit(guestId) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${guestId}/audit`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async getRecentAudit(limit = 50) {
    const res = await fetch(`${BACKEND_URL}/api/audit/recent?limit=${limit}`, { headers: authHeaders() });
    return handleResponse(res);
  },

  // Dashboard
  async getDashboardStats() {
    const res = await fetch(`${BACKEND_URL}/api/dashboard/stats`, { headers: authHeaders() });
    return handleResponse(res);
  },

  // Export
  async exportGuestsJson(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, v); });
    const res = await fetch(`${BACKEND_URL}/api/exports/guests.json?${query.toString()}`, { headers: authHeaders() });
    return handleResponse(res);
  },

  getExportCsvUrl(params = {}) {
    const query = new URLSearchParams();
    const token = getToken();
    Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, v); });
    return `${BACKEND_URL}/api/exports/guests.csv?${query.toString()}`;
  },

  // KVKK Compliance
  async getVerbisReport() {
    const res = await fetch(`${BACKEND_URL}/api/kvkk/verbis-report`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async getDataInventory() {
    const res = await fetch(`${BACKEND_URL}/api/kvkk/data-inventory`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async getRetentionWarnings() {
    const res = await fetch(`${BACKEND_URL}/api/kvkk/retention-warnings`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async getRightsRequests(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, v); });
    const res = await fetch(`${BACKEND_URL}/api/kvkk/rights-requests?${query.toString()}`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async createRightsRequest(data) {
    const res = await fetch(`${BACKEND_URL}/api/kvkk/rights-request`, {
      method: 'POST', headers: authHeaders(), body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  async processRightsRequest(requestId, data) {
    const res = await fetch(`${BACKEND_URL}/api/kvkk/rights-requests/${requestId}`, {
      method: 'PATCH', headers: authHeaders(), body: JSON.stringify(data),
    });
    return handleResponse(res);
  },

  async getGuestKvkkData(guestId) {
    const res = await fetch(`${BACKEND_URL}/api/kvkk/guest-data/${guestId}`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async getGuestPortableData(guestId) {
    const res = await fetch(`${BACKEND_URL}/api/kvkk/guest-data/${guestId}/portable`, { headers: authHeaders() });
    return handleResponse(res);
  },

  // API Guide
  async getApiGuide() {
    const res = await fetch(`${BACKEND_URL}/api/guide`, { headers: authHeaders() });
    return handleResponse(res);
  },

  // Review Queue
  async getReviewQueue(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => { if (v) query.set(k, v); });
    const res = await fetch(`${BACKEND_URL}/api/scans/review-queue?${query.toString()}`, { headers: authHeaders() });
    return handleResponse(res);
  },

  async updateScanReview(scanId, reviewStatus) {
    const res = await fetch(`${BACKEND_URL}/api/scans/${scanId}/review?review_status=${reviewStatus}`, {
      method: 'PATCH', headers: authHeaders(),
    });
    return handleResponse(res);
  },
};
