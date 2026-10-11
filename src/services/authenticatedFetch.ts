const AUTH_STORAGE_KEY = 'vitalguard.operator.session';

export function getOperatorAccessToken(): string | null {
  try {
    const raw = sessionStorage.getItem(AUTH_STORAGE_KEY);
    if (!raw) return null;
    const session = JSON.parse(raw) as { token?: string; expiresAt?: number };
    if (!session.token || !session.expiresAt || session.expiresAt <= Date.now()) {
      sessionStorage.removeItem(AUTH_STORAGE_KEY);
      return null;
    }
    return session.token;
  } catch {
    sessionStorage.removeItem(AUTH_STORAGE_KEY);
    return null;
  }
}

export function withOperatorAuth(init: RequestInit = {}): RequestInit {
  const headers = new Headers(init.headers);
  const token = getOperatorAccessToken();
  if (token) headers.set('Authorization', 'Bearer ' + token);
  return { ...init, headers };
}

export function authorizedFetch(input: RequestInfo | URL, init: RequestInit = {}): Promise<Response> {
  return fetch(input, withOperatorAuth(init));
}
