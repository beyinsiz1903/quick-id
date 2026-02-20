import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(() => {
    try {
      const stored = localStorage.getItem('quickid_user');
      return stored ? JSON.parse(stored) : null;
    } catch { return null; }
  });
  const [token, setToken] = useState(() => localStorage.getItem('quickid_token'));
  const [loading, setLoading] = useState(false);

  const login = useCallback((tokenStr, userData) => {
    localStorage.setItem('quickid_token', tokenStr);
    localStorage.setItem('quickid_user', JSON.stringify(userData));
    setToken(tokenStr);
    setUser(userData);
  }, []);

  const logout = useCallback(() => {
    localStorage.removeItem('quickid_token');
    localStorage.removeItem('quickid_user');
    setToken(null);
    setUser(null);
  }, []);

  const isAdmin = user?.role === 'admin';
  const isAuthenticated = !!token && !!user;

  return (
    <AuthContext.Provider value={{ user, token, login, logout, isAdmin, isAuthenticated, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within AuthProvider');
  return ctx;
}
