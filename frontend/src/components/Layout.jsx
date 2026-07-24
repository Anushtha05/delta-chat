import { useState, useEffect } from 'react';
import { Outlet, NavLink } from 'react-router-dom';
import { getHealth } from '../lib/api';

function StatusDot({ healthy }) {
  return (
    <span className="relative flex h-2.5 w-2.5">
      {healthy && (
        <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-success opacity-75" />
      )}
      <span className={`relative inline-flex rounded-full h-2.5 w-2.5 ${healthy ? 'bg-success' : 'bg-danger'}`} />
    </span>
  );
}

function Header() {
  const [healthy, setHealthy] = useState(false);

  useEffect(() => {
    const check = async () => {
      try {
        const data = await getHealth();
        setHealthy(data.mysql && data.mongo);
      } catch {
        setHealthy(false);
      }
    };
    check();
    const interval = setInterval(check, 15000);
    return () => clearInterval(interval);
  }, []);

  const linkClass = ({ isActive }) =>
    `px-3 py-2 rounded-md text-sm font-medium transition-colors ${
      isActive
        ? 'bg-accent-muted text-accent-light'
        : 'text-text-secondary hover:text-text-primary hover:bg-surface-700'
    }`;

  return (
    <header className="border-b border-surface-700 bg-surface-800/80 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex items-center justify-between h-14">
          <div className="flex items-center gap-3">
            <NavLink to="/" className="flex items-center gap-2">
              <svg className="w-6 h-6 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
              </svg>
              <span className="font-semibold text-lg text-text-primary">Delta Chat</span>
            </NavLink>
          </div>

          <nav className="hidden sm:flex items-center gap-1">
            <NavLink to="/compare" className={linkClass}>Compare</NavLink>
            <NavLink to="/chat" className={linkClass}>Chat</NavLink>
            <NavLink to="/evaluation" className={linkClass}>Evaluation</NavLink>
          </nav>

          <div className="flex items-center gap-2 text-xs text-text-muted">
            <StatusDot healthy={healthy} />
            <span className="hidden sm:inline">{healthy ? 'Systems online' : 'Offline'}</span>
          </div>
        </div>
      </div>
    </header>
  );
}

function Footer() {
  return (
    <footer className="border-t border-surface-700 bg-surface-800/50 mt-auto">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-6">
        <div className="flex flex-col sm:flex-row items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <svg className="w-4 h-4 text-accent" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z" />
            </svg>
            <span className="text-sm text-text-secondary">
              Delta Chat — Engineering document comparison with grounded AI
            </span>
          </div>
          <div className="flex items-center gap-4 text-xs text-text-muted">
            <a href="#" className="hover:text-accent transition-colors">GitHub</a>
            <a href="#" className="hover:text-accent transition-colors">Docs</a>
            <span>© 2024 Delta Chat</span>
          </div>
        </div>
      </div>
    </footer>
  );
}

export default function Layout() {
  return (
    <div className="min-h-screen flex flex-col">
      <Header />
      <main className="flex-1">
        <Outlet />
      </main>
      <Footer />
    </div>
  );
}
