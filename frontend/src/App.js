import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { Toaster } from './components/ui/sonner';
import AppShell from './components/AppShell';
import Dashboard from './pages/Dashboard';
import ScanPage from './pages/ScanPage';
import BulkScanPage from './pages/BulkScanPage';
import GuestList from './pages/GuestList';
import GuestDetail from './pages/GuestDetail';
import './App.css';

function App() {
  return (
    <Router>
      <AppShell>
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/scan" element={<ScanPage />} />
          <Route path="/bulk-scan" element={<BulkScanPage />} />
          <Route path="/guests" element={<GuestList />} />
          <Route path="/guests/:id" element={<GuestDetail />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </AppShell>
      <Toaster richColors position="top-right" />
    </Router>
  );
}

export default App;
