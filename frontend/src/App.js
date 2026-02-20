import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import { AuthProvider, useAuth } from './lib/AuthContext';
import AppShell from './components/AppShell';
import LoginPage from './pages/LoginPage';
import Dashboard from './pages/Dashboard';
import ScanPage from './pages/ScanPage';
import BulkScanPage from './pages/BulkScanPage';
import GuestList from './pages/GuestList';
import GuestDetail from './pages/GuestDetail';
import UserManagement from './pages/UserManagement';
import SettingsPage from './pages/SettingsPage';
import './App.css';

function ProtectedRoute({ children, adminOnly = false }) {
  const { isAuthenticated, isAdmin } = useAuth();
  if (!isAuthenticated) return <Navigate to="/login" replace />;
  if (adminOnly && !isAdmin) return <Navigate to="/" replace />;
  return children;
}

function AppRoutes() {
  const { isAuthenticated } = useAuth();

  return (
    <Routes>
      <Route path="/login" element={isAuthenticated ? <Navigate to="/" replace /> : <LoginPage />} />
      <Route path="/" element={<ProtectedRoute><AppShell><Dashboard /></AppShell></ProtectedRoute>} />
      <Route path="/scan" element={<ProtectedRoute><AppShell><ScanPage /></AppShell></ProtectedRoute>} />
      <Route path="/bulk-scan" element={<ProtectedRoute><AppShell><BulkScanPage /></AppShell></ProtectedRoute>} />
      <Route path="/guests" element={<ProtectedRoute><AppShell><GuestList /></AppShell></ProtectedRoute>} />
      <Route path="/guests/:id" element={<ProtectedRoute><AppShell><GuestDetail /></AppShell></ProtectedRoute>} />
      <Route path="/users" element={<ProtectedRoute adminOnly><AppShell><UserManagement /></AppShell></ProtectedRoute>} />
      <Route path="/settings" element={<ProtectedRoute adminOnly><AppShell><SettingsPage /></AppShell></ProtectedRoute>} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

function App() {
  return (
    <AuthProvider>
      <Router>
        <AppRoutes />
        <Toaster richColors position="top-right" />
      </Router>
    </AuthProvider>
  );
}

export default App;
