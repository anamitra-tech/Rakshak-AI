import { useState } from 'react';
import { GoogleLogin } from '@react-oauth/google';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { MOCK_CREDENTIALS } from '../context/mockCredentials';

const ROLES = [
  { id: 'citizen', label: 'Citizen', home: '/citizen/fraud-shield' },
  { id: 'government', label: 'Government & Police', home: '/command' },
];

const Login = () => {
  const { loginWithGoogleCredential, loginWithMockCredentials, loginAsDemo } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const [role, setRole] = useState('citizen');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState(null);

  const activeRole = ROLES.find((r) => r.id === role);
  const redirectTo = location.state?.from?.pathname || activeRole.home;

  const goAfterLogin = () => navigate(redirectTo, { replace: true });

  const handleRoleChange = (nextRole) => {
    setRole(nextRole);
    setError(null);
    setEmail('');
    setPassword('');
  };

  const handleGoogleSuccess = async (credentialResponse) => {
    setError(null);
    try {
      await loginWithGoogleCredential(credentialResponse.credential, role);
      goAfterLogin();
    } catch (e) {
      setError(e.message || 'Sign-in failed. Please try again.');
    }
  };

  const handleMockSubmit = (e) => {
    e.preventDefault();
    setError(null);
    try {
      loginWithMockCredentials(email, password, role);
      goAfterLogin();
    } catch (e) {
      setError(e.message);
    }
  };

  const handleFillDemoCreds = () => {
    const creds = MOCK_CREDENTIALS[role];
    setEmail(creds.email);
    setPassword(creds.password);
    setError(null);
  };

  const handleViewDemo = () => {
    loginAsDemo(role);
    goAfterLogin();
  };

  const creds = MOCK_CREDENTIALS[role];

  return (
    <div className="relative min-h-screen w-full overflow-hidden bg-[#041E24] flex items-center justify-center px-4 py-12">
      {/* Ambient background, matches landing page hero */}
      <div className="absolute inset-0 bg-[radial-gradient(circle_at_50%_35%,rgba(0,255,230,0.16),transparent_65%)]" />
      <div className="absolute inset-0 bg-gradient-to-r from-transparent via-cyan-300/5 to-transparent" />
      <div className="absolute bottom-0 left-0 w-full h-64 bg-gradient-to-t from-[#041E24] via-[#072A32]/60 to-transparent" />

      <Link
        to="/"
        className="absolute top-8 left-8 inline-flex items-center gap-3 rounded-full border border-cyan-300/30 bg-white/5 backdrop-blur-xl px-5 py-2 z-10"
      >
        <div className="h-2 w-2 rounded-full bg-cyan-300 animate-pulse" />
        <span className="text-sm font-medium text-cyan-100">PRAHARI</span>
      </Link>

      <div className="relative z-10 w-full max-w-md rounded-2xl border border-cyan-300/20 bg-white/5 backdrop-blur-2xl px-10 py-10 shadow-[0_0_80px_rgba(4,30,36,0.9)]">
        <h1 className="text-4xl font-bebas tracking-wide font-black text-white text-center">
          Welcome to <span className="text-cyan-300">Prahari</span>
        </h1>
        <p className="mt-3 text-center text-sm text-slate-300">
          Sign in as a citizen, or as a government / police official using CommandWorkspace.
        </p>

        {/* Role tabs */}
        <div className="mt-6 grid grid-cols-2 gap-2 rounded-xl border border-cyan-300/20 bg-black/20 p-1">
          {ROLES.map((r) => (
            <button
              key={r.id}
              type="button"
              onClick={() => handleRoleChange(r.id)}
              className={`rounded-lg py-2 text-sm font-medium transition ${
                role === r.id
                  ? 'bg-cyan-400/90 text-[#041E24]'
                  : 'text-slate-300 hover:text-cyan-200'
              }`}
            >
              {r.label}
            </button>
          ))}
        </div>

        {/* Mock credential login */}
        <form onSubmit={handleMockSubmit} className="mt-6 space-y-3">
          <input
            type="email"
            placeholder="Email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            className="w-full rounded-lg border border-cyan-300/20 bg-black/20 px-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-300/50"
          />
          <input
            type="password"
            placeholder="Password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            className="w-full rounded-lg border border-cyan-300/20 bg-black/20 px-4 py-2.5 text-sm text-white placeholder:text-slate-500 focus:outline-none focus:border-cyan-300/50"
          />
          <button
            type="submit"
            className="w-full rounded-lg bg-cyan-400/90 hover:bg-cyan-300 transition py-2.5 text-sm font-semibold text-[#041E24]"
          >
            Sign in as {activeRole.label}
          </button>
        </form>

        <div className="mt-3 rounded-lg border border-cyan-300/10 bg-cyan-300/5 px-4 py-3 text-xs text-slate-400">
          <div className="flex items-center justify-between gap-2">
            <span>
              Demo credentials: <span className="text-cyan-200">{creds.email}</span> /{' '}
              <span className="text-cyan-200">{creds.password}</span>
            </span>
            <button
              type="button"
              onClick={handleFillDemoCreds}
              className="shrink-0 text-cyan-300 hover:text-cyan-200 underline underline-offset-2"
            >
              Fill in
            </button>
          </div>
        </div>

        {error && (
          <div className="mt-4 p-3 border border-red-400/30 bg-red-500/10 text-red-300 rounded-xl text-sm text-center">
            {error}
          </div>
        )}

        <div className="mt-6 flex items-center gap-3">
          <div className="h-px flex-1 bg-cyan-300/15" />
          <span className="text-xs text-slate-500">or</span>
          <div className="h-px flex-1 bg-cyan-300/15" />
        </div>

        <div className="mt-4 flex justify-center">
          <GoogleLogin
            onSuccess={handleGoogleSuccess}
            onError={() => setError('Google sign-in failed. Please try again.')}
            theme="filled_black"
            shape="pill"
            size="large"
          />
        </div>

        <button
          type="button"
          onClick={handleViewDemo}
          className="mt-6 w-full rounded-lg border border-cyan-300/25 py-2.5 text-sm font-medium text-cyan-200 hover:bg-cyan-300/10 transition"
        >
          Skip login — view {activeRole.label} demo data
        </button>

        <p className="mt-6 text-center text-xs text-slate-400">
          New to Prahari? Continuing with Google creates your account automatically —
          no separate sign-up needed.
        </p>
      </div>
    </div>
  );
};

export default Login;
