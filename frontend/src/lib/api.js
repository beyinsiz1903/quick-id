const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || '';

export const api = {
  // Scan
  async scanId(imageBase64) {
    const res = await fetch(`${BACKEND_URL}/api/scan`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ image_base64: imageBase64 }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Scan failed' }));
      throw new Error(err.detail || 'Scan failed');
    }
    return res.json();
  },

  // Scans history
  async getScans(page = 1, limit = 20) {
    const res = await fetch(`${BACKEND_URL}/api/scans?page=${page}&limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch scans');
    return res.json();
  },

  // Duplicate check
  async checkDuplicate(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') query.set(k, v);
    });
    const res = await fetch(`${BACKEND_URL}/api/guests/check-duplicate?${query.toString()}`);
    if (!res.ok) throw new Error('Duplicate check failed');
    return res.json();
  },

  // Guests
  async createGuest(data) {
    const res = await fetch(`${BACKEND_URL}/api/guests`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Create failed' }));
      throw new Error(err.detail || 'Create failed');
    }
    return res.json();
  },

  async getGuests(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v !== null && v !== undefined && v !== '') query.set(k, v);
    });
    const res = await fetch(`${BACKEND_URL}/api/guests?${query.toString()}`);
    if (!res.ok) throw new Error('Failed to fetch guests');
    return res.json();
  },

  async getGuest(id) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}`);
    if (!res.ok) throw new Error('Guest not found');
    return res.json();
  },

  async updateGuest(id, data) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}`, {
      method: 'PATCH',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(data),
    });
    if (!res.ok) throw new Error('Update failed');
    return res.json();
  },

  async deleteGuest(id) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}`, { method: 'DELETE' });
    if (!res.ok) throw new Error('Delete failed');
    return res.json();
  },

  async checkinGuest(id) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}/checkin`, { method: 'POST' });
    if (!res.ok) throw new Error('Check-in failed');
    return res.json();
  },

  async checkoutGuest(id) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${id}/checkout`, { method: 'POST' });
    if (!res.ok) throw new Error('Check-out failed');
    return res.json();
  },

  // Audit Trail
  async getGuestAudit(guestId) {
    const res = await fetch(`${BACKEND_URL}/api/guests/${guestId}/audit`);
    if (!res.ok) throw new Error('Failed to fetch audit logs');
    return res.json();
  },

  async getRecentAudit(limit = 50) {
    const res = await fetch(`${BACKEND_URL}/api/audit/recent?limit=${limit}`);
    if (!res.ok) throw new Error('Failed to fetch audit logs');
    return res.json();
  },

  // Dashboard
  async getDashboardStats() {
    const res = await fetch(`${BACKEND_URL}/api/dashboard/stats`);
    if (!res.ok) throw new Error('Failed to fetch stats');
    return res.json();
  },

  // Export
  async exportGuestsJson(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) query.set(k, v);
    });
    const res = await fetch(`${BACKEND_URL}/api/exports/guests.json?${query.toString()}`);
    if (!res.ok) throw new Error('Export failed');
    return res.json();
  },

  getExportCsvUrl(params = {}) {
    const query = new URLSearchParams();
    Object.entries(params).forEach(([k, v]) => {
      if (v) query.set(k, v);
    });
    return `${BACKEND_URL}/api/exports/guests.csv?${query.toString()}`;
  },
};
