import cohortData from '../../backend/app/data/cohort.json';
import { APP_CONFIG } from './config.ts';

/**
 * Demo sign-in and role-based access (fictional staff from backend/app/data/cohort.json).
 *
 * With the backend reachable, sign-in returns a signed bearer token and the backend
 * enforces every role rule. Offline, the same accounts open a local-only session with
 * no token: the UI still applies the role rules, but nothing is sent to the API.
 *
 * The session lives in localStorage so an installed app stays signed in between
 * launches (needed for that doctor's alert notifications); signing out clears it.
 */
export type Role = 'admin' | 'nurse' | 'doctor';
export interface StaffMember { username: string; display_name: string; role: Role; wards: string[] }
export interface Session { username: string; displayName: string; role: Role; wards: string[]; token: string | null; expiresAt: number | null }

export const STAFF = cohortData.staff as StaffMember[];
export const DEMO_PASSWORD = 'demo-access';
const STORAGE_KEY = 'vg-session';
const LEGACY_KEY = 'vg-demo-session';
const listeners = new Set<() => void>();
// Parsed once per change so React's useSyncExternalStore gets a stable snapshot.
let cached: Session | null | undefined;

/** Which parts of the app each role may open. Keep in sync with the backend checks in auth.py. */
export const ACCESS = {
  dashboard: ['admin', 'nurse', 'doctor'],
  patients: ['admin', 'nurse', 'doctor'],
  alerts: ['admin', 'nurse', 'doctor'],
  liveDemo: ['admin', 'nurse'],
  analytics: ['admin', 'doctor'],
  modelPerformance: ['admin', 'doctor'],
  settings: ['admin', 'nurse', 'doctor'],
  // Finer-grained actions and settings panels.
  controlStream: ['admin', 'nurse'],
  acknowledgeAlert: ['admin', 'nurse', 'doctor'],
  resolveAlert: ['admin', 'doctor'],
  modelTools: ['admin', 'doctor'],
  systemSettings: ['admin'],
  staffDirectory: ['admin'],
} as const satisfies Record<string, readonly Role[]>;
export type Permission = keyof typeof ACCESS;

export const ROLE_SUMMARY: Record<Role, string> = {
  admin: 'Full access: live stream control, every patient, model performance, staff and system settings.',
  nurse: 'All wards: monitoring, live stream control and alert acknowledgement.',
  doctor: 'Assigned patients only: their alerts (acknowledge and resolve), push notifications and model insights.',
};

export function can(session: Pick<Session, 'role'> | null, permission: Permission): boolean {
  return !!session && (ACCESS[permission] as readonly Role[]).includes(session.role);
}

function read(): Session | null {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') as Session | null;
    return value && STAFF.some((member) => member.username === value.username && member.role === value.role) ? value : null;
  } catch {
    return null;
  }
}

export function getSession(): Session | null {
  if (cached === undefined) cached = read();
  if (cached?.expiresAt && cached.expiresAt < Date.now()) { store(null); return null; }
  return cached;
}

function store(session: Session | null) {
  try {
    if (session) localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
    else localStorage.removeItem(STORAGE_KEY);
    sessionStorage.removeItem(LEGACY_KEY);
  } catch { /* storage unavailable: the session lasts for this page only */ }
  cached = session;
  listeners.forEach((listener) => listener());
}

export function clearSession() { store(null); }

export function onSessionChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}

// Signing in or out in another tab of the same app applies here too.
if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event) => {
    if (event.key !== STORAGE_KEY && event.key !== null) return;
    cached = undefined;
    listeners.forEach((listener) => listener());
  });
}

export class SignInError extends Error {}

/** Local-only session (no token): used when the backend cannot be reached, and in tests. */
export function openOfflineSession(username: string): Session {
  const member = STAFF.find((item) => item.username === username);
  if (!member) throw new SignInError('Unknown username.');
  const session: Session = { username: member.username, displayName: member.display_name, role: member.role,
    wards: member.wards, token: null, expiresAt: null };
  store(session);
  return session;
}

/** Backend sign-in; falls back to a local-only session when the API cannot be reached. */
export async function signIn(username: string, password: string): Promise<Session> {
  const member = STAFF.find((item) => item.username === username.trim().toLowerCase());
  let response: Response;
  try {
    response = await fetch(`${APP_CONFIG.apiBaseUrl}/api/v1/auth/login`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username, password }), signal: AbortSignal.timeout(8000),
    });
  } catch {
    if (!member || password !== DEMO_PASSWORD) throw new SignInError('Unknown username or wrong password.');
    return openOfflineSession(member.username);
  }
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string };
    throw new SignInError(body.detail || `Sign-in failed (${response.status})`);
  }
  const body = await response.json() as { token: string; expires_in: number; user: StaffMember };
  const session: Session = { username: body.user.username, displayName: body.user.display_name, role: body.user.role,
    wards: body.user.wards, token: body.token, expiresAt: Date.now() + body.expires_in * 1000 };
  store(session);
  return session;
}

/** Authorization header for API calls, when signed in against the backend. */
export function authHeaders(): Record<string, string> {
  const token = getSession()?.token;
  return token ? { Authorization: `Bearer ${token}` } : {};
}

/** Called when the API rejects the token (expired, or the server restarted with a new secret). */
export function handleUnauthorized() {
  if (getSession()?.token) clearSession();
}
