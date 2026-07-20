// src/Dashboard/CommandWorkSpace/CommandLayout.jsx
import { Outlet, NavLink, useNavigate } from 'react-router-dom';
import { Network, MapPinned, ShieldAlert, LogOut, Radar } from 'lucide-react';
import { useAuth } from '../../context/AuthContext';

const navItems = [
  { to: '/command/network', label: 'Fraud Network', icon: Network },
  { to: '/command/geospatial', label: 'Geospatial', icon: MapPinned },
  { to: '/command/digital-arrest', label: 'Digital Arrest', icon: ShieldAlert },
];

const CommandLayout = () => {
  const { user, logout } = useAuth();
  const navigate = useNavigate();

  const handleLogout = async () => {
    await logout();
    navigate('/');
  };

  return (
    <div className="min-h-screen flex bg-[#020d10] text-white relative overflow-hidden font-sans">
      {/* Dynamic Animated Ambient Glows */}
      <div className="pointer-events-none absolute -top-40 -left-40 h-[500px] w-[500px] rounded-full bg-cyan-500/20 blur-[140px] animate-pulse [animation-duration:8s]" />
      <div className="pointer-events-none absolute top-1/3 right-1/4 h-[600px] w-[600px] rounded-full bg-blue-500/10 blur-[160px] animate-bounce [animation-duration:15s]" />
      <div className="pointer-events-none absolute -bottom-20 -right-20 h-96 w-96 rounded-full bg-amber-500/10 blur-[120px] animate-pulse [animation-duration:6s]" />

      {/* Modern Cyber Glassmorphic Sidebar */}
      <aside className="relative w-64 border-r border-cyan-500/20 bg-[#041a1f]/70 backdrop-blur-md p-5 flex flex-col justify-between shadow-[4px_0_24px_rgba(6,182,212,0.05)] z-10">
        <div>
          {/* Header Branding */}
          <div className="px-2 mb-8 group cursor-pointer">
            <div className="flex items-center gap-2.5">
              <div className="relative">
                <Radar className="h-5 w-5 text-cyan-400 animate-spin [animation-duration:10s]" />
                <span className="absolute inset-0 rounded-full bg-cyan-400/30 animate-ping" />
              </div>
              <span className="text-cyan-200 font-bold tracking-widest text-sm transition-colors group-hover:text-cyan-400">
                PRAHARI <span className="text-cyan-600 font-medium text-xs ml-1">// CMD</span>
              </span>
            </div>
            <div className="mt-4 h-[2px] w-full bg-gradient-to-r from-cyan-500 via-cyan-500/30 to-transparent shadow-[0_1px_3px_rgba(6,182,212,0.4)]" />
          </div>

          {/* Navigation Items */}
          <nav className="space-y-2">
            {navItems.map(({ to, label, icon: Icon }) => (
              <NavLink
                key={to}
                to={to}
                className={({ isActive }) =>
                  `group relative flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-semibold transition-all duration-300 transform active:scale-95 ${
                    isActive
                      ? 'bg-gradient-to-r from-cyan-500/20 to-transparent text-cyan-300 shadow-[inset_1px_1px_0_rgba(34,211,238,0.3)] border-l-2 border-cyan-400'
                      : 'text-slate-400 hover:text-cyan-200 hover:bg-white/[0.02] border-l-2 border-transparent'
                  }`
                }
              >
                {({ isActive }) => (
                  <>
                    <Icon
                      className={`h-4 w-4 shrink-0 transition-all duration-300 ${
                        isActive 
                          ? 'text-cyan-400 drop-shadow-[0_0_8px_rgba(34,211,238,0.8)] scale-110' 
                          : 'text-slate-500 group-hover:text-cyan-400 group-hover:scale-110'
                      }`}
                    />
                    <span className="tracking-wide">{label}</span>
                    
                    {/* Decorative active glow indicators */}
                    {isActive && (
                      <span className="absolute right-3 top-1/2 -translate-y-1/2 w-1.5 h-1.5 rounded-full bg-cyan-400 drop-shadow-[0_0_6px_rgba(34,211,238,1)]" />
                    )}
                  </>
                )}
              </NavLink>
            ))}
          </nav>
        </div>

        {/* User Profile & Action Footer */}
        {user && (
          <div className="pt-4 border-t border-cyan-500/15">
            <div className="flex items-center gap-3 mb-4 px-3 py-2.5 rounded-xl bg-gradient-to-b from-white/[0.04] to-transparent border border-white/[0.02] shadow-sm">
              {user.picture ? (
                <img src={user.picture} alt="" className="h-8 w-8 rounded-full ring-2 ring-cyan-500/40 shadow-md" />
              ) : (
                <div className="h-8 w-8 rounded-full bg-gradient-to-br from-cyan-500/30 to-cyan-600/10 flex items-center justify-center text-xs font-bold text-cyan-300 shadow-inner">
                  {user.name?.[0]?.toUpperCase()}
                </div>
              )}
              <div className="min-w-0 flex-1">
                <div className="text-xs font-bold text-slate-200 truncate leading-tight tracking-wide">{user.name}</div>
                <div className="flex items-center gap-1.5 text-[10px] text-emerald-400 font-medium mt-0.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,1)] animate-pulse" />
                  SYSTEM ACTIVE
                </div>
              </div>
            </div>
            
            <button
              onClick={handleLogout}
              className="w-full flex items-center justify-center gap-2 text-xs font-medium text-slate-400 hover:text-amber-400 hover:bg-amber-500/5 transition-all duration-200 py-2 rounded-lg border border-transparent hover:border-amber-500/20"
            >
              <LogOut className="h-3.5 w-3.5" />
              Terminate Session
            </button>
          </div>
        )}
      </aside>

      {/* Main Workspace Dashboard Canvas */}
      <main className="relative flex-1 p-8 overflow-y-auto bg-gradient-to-tr from-transparent via-[#051c22]/10 to-transparent">
        {/* Subtle grid backdrop overlay for a high-tech vibe */}
        <div className="absolute inset-0 bg-[linear-gradient(to_right,#06b6d403_1px,transparent_1px),linear-gradient(to_bottom,#06b6d403_1px,transparent_1px)] bg-[size:4rem_4rem] pointer-events-none" />
        
        {/* Actual Content */}
        <div className="relative z-10 h-full">
          <Outlet />
        </div>
      </main>
    </div>
  );
};

export default CommandLayout;