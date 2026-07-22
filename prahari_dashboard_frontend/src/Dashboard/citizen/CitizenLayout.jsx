// src/Dashboard/citizen/CitizenLayout.jsx
import { useState, useEffect } from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';
import prahariLogo from '../../prahari copy 2.png'; 

const navItems = [
  { to: '/citizen/fraud-shield', label: 'Fraud Shield' },
  { to: '/citizen/report', label: 'Report a Scam' },
];

const CitizenLayout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    window.addEventListener('scroll', onScroll);
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  const navLinkClass = ({ isActive }) =>
    `relative py-1 font-medium text-sm transition-colors duration-200 ${
      isActive ? 'text-cyan-700' : 'text-slate-600 hover:text-slate-900'
    }`;

  return (
    // Lowered base brightness with slate-100 to give the components depth
    <div className="min-h-screen bg-slate-100 text-slate-900 font-sans antialiased">
      
      {/* Premium, distinct Navbar with background blur and subtle shadow */}
      <header
        className={`sticky top-0 z-50 flex items-center justify-between px-6 md:px-12 py-4 border-b transition-all duration-300 ${
          scrolled
            ? 'bg-white/85 backdrop-blur-md border-slate-200 shadow-sm'
            : 'bg-white border-slate-200 shadow-xs'
        }`}
      >
        <NavLink to="/" className="font-bold flex items-center gap-2.5 text-slate-900 tracking-tight">
          <img src={prahariLogo} alt="Prahari Logo" className="h-8 w-8 object-contain" />
          <span className="text-xl">Prahari</span>
        </NavLink>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8">
          <div className="flex items-center gap-6">
            {navItems.map((item) => (
              <NavLink key={item.to} to={item.to} className={navLinkClass}>
                {item.label}
                {/* Clean indicator line for the active tab */}
                {window.location.pathname.includes(item.to) && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-600 rounded-full" />
                )}
              </NavLink>
            ))}
          </div>

          <div className="flex items-center gap-4 pl-6 border-l border-slate-200">
            {/* Protection status pill — sleeker, more professional typography */}
            <span className="flex items-center gap-1.5 text-xs font-semibold text-emerald-700 bg-emerald-50/80 border border-emerald-200 px-3 py-1 rounded-full tracking-wide">
              <span className="relative flex h-1.5 w-1.5">
                <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex rounded-full h-1.5 w-1.5 bg-emerald-500" />
              </span>
              Protected
            </span>

            {user && (
              <div className="flex items-center gap-3">
                {user.picture ? (
                  <img src={user.picture} alt="" className="h-8 w-8 rounded-full border border-slate-200" />
                ) : (
                  <div className="h-8 w-8 rounded-full bg-slate-100 text-slate-700 border border-slate-200 flex items-center justify-center text-xs font-bold">
                    {user.name?.[0]?.toUpperCase() || 'D'}
                  </div>
                )}
                <span className="text-sm font-medium text-slate-700">{user.name || 'Demo Citizen'}</span>
                <button
                  onClick={handleLogout}
                  className="text-sm font-medium text-slate-400 hover:text-red-600 transition-colors duration-200 ml-1"
                >
                  Logout
                </button>
              </div>
            )}
          </div>
        </nav>

        {/* Mobile toggle */}
        <button
          className="md:hidden text-slate-600"
          onClick={() => setMenuOpen((v) => !v)}
          aria-label="Toggle menu"
        >
          {menuOpen ? '✕' : '☰'}
        </button>
      </header>

      {/* Mobile nav */}
      {menuOpen && (
        <nav className="md:hidden flex flex-col gap-4 px-6 py-4 bg-white border-b border-slate-200 text-sm shadow-md">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              onClick={() => setMenuOpen(false)}
              className={navLinkClass}
            >
              {item.label}
            </NavLink>
          ))}
          {user && (
            <button
              onClick={handleLogout}
              className="text-left text-slate-500 hover:text-red-600 transition pt-2 border-t border-slate-100"
            >
              Logout
            </button>
          )}
        </nav>
      )}

      {/* Main content wrapper containing page outlets */}
      <main className="max-w-7xl mx-auto px-6 md:px-12 py-10">
        <Outlet />
      </main>
    </div>
  );
};

export default CitizenLayout;