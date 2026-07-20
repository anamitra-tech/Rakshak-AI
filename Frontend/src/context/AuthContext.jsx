import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { MOCK_CREDENTIALS } from './mockCredentials';

const AuthContext = createContext(null);

const MOCK_SESSION_KEY = 'prahari_mock_user';

const readStoredMockUser = () => {
  try {
    const stored = sessionStorage.getItem(MOCK_SESSION_KEY);
    return stored ? JSON.parse(stored) : null;
  } catch {
    return null;
  }
};

export const AuthProvider = ({ children }) => {
  const [user, setUser] = useState(readStoredMockUser);
  const [loading, setLoading] = useState(() => !readStoredMockUser());

  const refreshUser = useCallback(async () => {
    try {
      const res = await fetch('/api/auth/me', { credentials: 'include' });
      if (res.ok) {
        setUser(await res.json());
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    // A mock/demo session is entirely local — no need to check the backend cookie.
    if (readStoredMockUser()) return;
    refreshUser();
  }, [refreshUser]);

  const loginWithGoogleCredential = useCallback(async (credential, role = 'citizen') => {
    const res = await fetch('/api/auth/google', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      credentials: 'include',
      body: JSON.stringify({ credential }),
    });
    if (!res.ok) {
      const err = await res.json().catch(() => null);
      throw new Error(err?.detail || `Sign-in failed (${res.status})`);
    }
    const data = await res.json();
    const taggedUser = { ...data, role };
    sessionStorage.removeItem(MOCK_SESSION_KEY);
    setUser(taggedUser);
    return taggedUser;
  }, []);

  const loginWithMockCredentials = useCallback((email, password, role) => {
    const creds = MOCK_CREDENTIALS[role];
    if (!creds || email.trim().toLowerCase() !== creds.email || password !== creds.password) {
      throw new Error('Incorrect email or password for this role. Use the demo credentials shown below.');
    }
    const mockUser = { email: creds.email, name: creds.name, picture: null, role, isMock: true };
    sessionStorage.setItem(MOCK_SESSION_KEY, JSON.stringify(mockUser));
    setUser(mockUser);
    return mockUser;
  }, []);

  const loginAsDemo = useCallback((role) => {
    const demoUser =
      role === 'government'
        ? { email: 'demo.official@prahari.in', name: 'Demo Official (View Only)', picture: null, role, isDemo: true }
        : { email: 'demo.citizen@prahari.in', name: 'Demo Citizen (View Only)', picture: null, role, isDemo: true };
    sessionStorage.setItem(MOCK_SESSION_KEY, JSON.stringify(demoUser));
    setUser(demoUser);
    return demoUser;
  }, []);

  const logout = useCallback(async () => {
    const isLocalOnly = Boolean(user?.isMock || user?.isDemo);
    sessionStorage.removeItem(MOCK_SESSION_KEY);
    if (!isLocalOnly) {
      await fetch('/api/auth/logout', { method: 'POST', credentials: 'include' });
    }
    setUser(null);
  }, [user]);

  return (
    <AuthContext.Provider
      value={{ user, loading, loginWithGoogleCredential, loginWithMockCredentials, loginAsDemo, logout }}
    >
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error('useAuth must be used within an AuthProvider');
  return ctx;
};
