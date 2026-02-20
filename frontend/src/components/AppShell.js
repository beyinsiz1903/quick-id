import React, { useState } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { Button } from './ui/button';
import { Sheet, SheetContent, SheetTrigger } from './ui/sheet';
import {
  LayoutDashboard,
  ScanLine,
  Users,
  Layers,
  Menu,
  CreditCard,
} from 'lucide-react';

const navItems = [
  { path: '/', label: 'Genel Bakış', icon: LayoutDashboard },
  { path: '/scan', label: 'Tara', icon: ScanLine },
  { path: '/bulk-scan', label: 'Toplu Tarama', icon: Layers },
  { path: '/guests', label: 'Misafirler', icon: Users },
];

export default function AppShell({ children }) {
  const location = useLocation();
  const [mobileOpen, setMobileOpen] = useState(false);

  const isActive = (path) => {
    if (path === '/') return location.pathname === '/';
    return location.pathname.startsWith(path);
  };

  const NavLinks = ({ onNavigate }) => (
    <nav className="flex flex-col gap-1" data-testid="sidebar-nav">
      {navItems.map((item) => (
        <Link
          key={item.path}
          to={item.path}
          onClick={onNavigate}
          className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors duration-150 ${
            isActive(item.path)
              ? 'bg-[var(--brand-sky-soft)] text-[var(--brand-sky)]'
              : 'text-[var(--brand-slate)] hover:bg-[hsl(var(--secondary))] hover:text-[var(--brand-ink)]'
          }`}
        >
          <item.icon className="w-5 h-5" />
          {item.label}
        </Link>
      ))}
    </nav>
  );

  return (
    <div className="min-h-screen bg-[hsl(var(--background))] noise-bg">
      {/* Desktop Sidebar */}
      <aside className="hidden lg:fixed lg:flex lg:flex-col lg:w-64 lg:h-screen border-r border-[hsl(var(--border))] bg-white z-20">
        <div className="p-5 border-b border-[hsl(var(--border))]">
          <Link to="/" className="flex items-center gap-2.5">
            <div className="w-9 h-9 rounded-xl bg-[var(--brand-sky)] flex items-center justify-center">
              <CreditCard className="w-5 h-5 text-white" />
            </div>
            <div>
              <h1 className="text-base font-semibold text-[var(--brand-ink)]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
                Quick ID
              </h1>
              <p className="text-[10px] text-[var(--brand-slate)] -mt-0.5">Kimlik Okuyucu</p>
            </div>
          </Link>
        </div>
        <div className="flex-1 p-3 overflow-y-auto">
          <NavLinks />
        </div>
        <div className="p-4 border-t border-[hsl(var(--border))]">
          <p className="text-xs text-[var(--brand-slate)]">
            Quick ID Reader v1.0
          </p>
        </div>
      </aside>

      {/* Mobile Header */}
      <header className="lg:hidden sticky top-0 z-30 flex items-center justify-between h-14 px-4 border-b border-[hsl(var(--border))] bg-white/95 backdrop-blur">
        <Link to="/" className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-[var(--brand-sky)] flex items-center justify-center">
            <CreditCard className="w-4 h-4 text-white" />
          </div>
          <span className="text-sm font-semibold text-[var(--brand-ink)]" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>
            Quick ID
          </span>
        </Link>
        <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
          <SheetTrigger asChild>
            <Button variant="ghost" size="icon" data-testid="mobile-nav-sheet-trigger">
              <Menu className="w-5 h-5" />
            </Button>
          </SheetTrigger>
          <SheetContent side="left" className="w-64 p-4">
            <div className="mb-6">
              <h2 className="text-lg font-semibold" style={{ fontFamily: "'Space Grotesk', sans-serif" }}>Quick ID</h2>
              <p className="text-xs text-muted-foreground">Kimlik Okuyucu</p>
            </div>
            <NavLinks onNavigate={() => setMobileOpen(false)} />
          </SheetContent>
        </Sheet>
      </header>

      {/* Main Content */}
      <main className="lg:ml-64 min-h-screen relative z-10">
        <div className="max-w-[1400px] mx-auto p-4 sm:p-6">
          {children}
        </div>
      </main>
    </div>
  );
}
