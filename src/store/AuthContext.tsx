import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from 'react';
import { APP_CONFIG } from '../services/config.ts';

type AuthState = { token: string; username: string; expiresAt: number };
type AuthContextValue = {
  token: string | null;
  username: string | null;
  login: (username: string, password: string) => Promise<void>;
  logout: () => void;
};
const STORAGE_KEY = 'vitalguard.operator.session';
const AuthContext = createContext<AuthContextValue | null>(null);

function readSession(): AuthState | null {
  try {
    const raw = sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return null;
    const value = JSON.parse(raw) as AuthState;
    if (!value.token || !value.username || value.expiresAt <= Date.now()) {
      sessionStorage.removeItem(STORAGE_KEY);
      return null;
    }
    return value;
  } catch {
    sessionStorage.removeItem(STORAGE_KEY);
    return null;
  }
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [session, setSession] = useState<AuthState | null>(() => readSession());
  const logout = useCallback(() => {
    sessionStorage.removeItem(STORAGE_KEY);
    setSession(null);
  }, []);
  const login = useCallback(async (username: string, password: string) => {
    const response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/auth/login`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }),
      signal: AbortSignal.timeout(8000),
    });
    if (!response.ok) {
      if (response.status === 503) throw new Error('Authentication is not configured on the server. Ask the operator to configure it in Render.');
      if (response.status === 401) throw new Error('Incorrect username or password.');
      throw new Error(`Login failed (${response.status}). Please try again.`);
    }
    const result = await response.json() as { access_token: string; expires_in: number };
    const next: AuthState = {
      token: result.access_token,
      username,
      expiresAt: Date.now() + result.expires_in * 1000,
    };
    sessionStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    setSession(next);
  }, []);
  const value = useMemo(() => ({
    token: session && session.expiresAt > Date.now() ? session.token : null,
    username: session && session.expiresAt > Date.now() ? session.username : null,
    login,
    logout,
  }), [session, login, logout]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
}

export function useOptionalAuth() {
  return useContext(AuthContext);
}
