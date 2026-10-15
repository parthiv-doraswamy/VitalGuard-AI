import { APP_CONFIG } from './config.ts';
import { authHeaders } from './auth.ts';

/**
 * Web Push opt-in for this browser (device-scoped; there are no user accounts).
 *
 * - Permission is only requested from an explicit user action (enablePush).
 * - The backend returns a management token once; it is kept in localStorage on this
 *   device and is required to change, test or remove the subscription.
 * - Unsupported browsers, denied permission and missing server configuration are normal,
 *   non-blocking states: alerts still appear in the in-app alert center.
 */
export type PushAvailability = 'supported' | 'unsupported' | 'needs-install' | 'insecure-context';
export type PushState =
  | { kind: 'unavailable'; reason: PushAvailability | 'server-not-configured' }
  | { kind: 'denied' }
  | { kind: 'off' }
  | { kind: 'revoked' }
  | { kind: 'on'; subscriptionId: string; minSeverity: Severity };
export type Severity = 'high' | 'critical';

export interface PushConfig { push_available: boolean; vapid_public_key: string | null }
export interface PushDelivery {
  delivery_id: number; kind: 'alert' | 'test'; alert_id: number | null; status: string; attempts: number;
  last_status_code: number | null; created_at: string | null; accepted_at: string | null;
  displayed_at: string | null; clicked_at: string | null;
}
interface StoredSubscription { subscriptionId: string; token: string; endpoint: string; minSeverity: Severity }

const STORAGE_KEY = 'vg-push-subscription';
const API = () => `${APP_CONFIG.apiBaseUrl}/api/v1/notifications`;

function readStored(): StoredSubscription | null {
  try {
    const value = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null') as StoredSubscription | null;
    return value?.subscriptionId && value.token ? value : null;
  } catch {
    return null;
  }
}
function writeStored(value: StoredSubscription | null) {
  try {
    if (value) localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    else localStorage.removeItem(STORAGE_KEY);
  } catch { /* storage unavailable: the subscription cannot be managed after reload */ }
}

export function pushAvailability(): PushAvailability {
  if (typeof window === 'undefined') return 'unsupported';
  if (!window.isSecureContext) return 'insecure-context';
  const standalone = window.matchMedia?.('(display-mode: standalone)').matches
    || (navigator as Navigator & { standalone?: boolean }).standalone === true;
  const ios = /iPad|iPhone|iPod/.test(navigator.userAgent) || (navigator.platform === 'MacIntel' && navigator.maxTouchPoints > 1);
  const hasApis = 'serviceWorker' in navigator && 'PushManager' in window && 'Notification' in window;
  // iOS/iPadOS 16.4+ only offers Web Push to web apps added to the Home Screen.
  if (ios && !standalone) return 'needs-install';
  return hasApis ? 'supported' : 'unsupported';
}

export function urlBase64ToUint8Array(base64: string): Uint8Array {
  const padded = (base64 + '='.repeat((4 - (base64.length % 4)) % 4)).replace(/-/g, '+').replace(/_/g, '/');
  return Uint8Array.from(atob(padded), (char) => char.charCodeAt(0));
}

async function request<T>(path: string, init: RequestInit & { token?: string; json?: unknown } = {}): Promise<T> {
  const { token, json, ...rest } = init;
  const headers = new Headers({ ...authHeaders(), ...Object.fromEntries(new Headers(rest.headers)) });
  if (json !== undefined) headers.set('Content-Type', 'application/json');
  if (token) headers.set('X-Subscription-Token', token);
  const response = await fetch(`${API()}${path}`, {
    ...rest, headers, body: json === undefined ? rest.body : JSON.stringify(json), signal: AbortSignal.timeout(10000),
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({})) as { detail?: string; error?: string };
    throw Object.assign(new Error(body.detail || `Request failed (${response.status})`), { status: response.status, code: body.error });
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}

export const getPushConfig = () => request<PushConfig>('/config');

async function registration(): Promise<ServiceWorkerRegistration> {
  const ready = navigator.serviceWorker.ready;
  const timeout = new Promise<never>((_, reject) => setTimeout(() => reject(new Error('The app service worker is not active yet; reload and try again.')), 10000));
  return Promise.race([ready, timeout]);
}

async function registerWithBackend(subscription: PushSubscription, minSeverity: Severity): Promise<StoredSubscription> {
  const body = await request<{ subscription: { subscription_id: string }; management_token: string }>('/subscriptions', {
    method: 'POST', json: { subscription: subscription.toJSON(), min_severity: minSeverity },
  });
  const stored = { subscriptionId: body.subscription.subscription_id, token: body.management_token,
    endpoint: subscription.endpoint, minSeverity };
  writeStored(stored);
  return stored;
}

/** Current state without prompting. Repairs a rotated/revoked browser subscription when permission still allows. */
export async function reconcilePush(): Promise<PushState> {
  const availability = pushAvailability();
  if (availability !== 'supported') return { kind: 'unavailable', reason: availability };
  const stored = readStored();
  if (Notification.permission === 'denied') {
    if (stored) {
      // Permission was revoked in browser settings: stop server-side sends to this device.
      await request(`/subscriptions/${stored.subscriptionId}`, { method: 'DELETE', token: stored.token }).catch(() => undefined);
      writeStored(null);
    }
    return { kind: 'denied' };
  }
  if (!stored) return { kind: 'off' };
  const browserSubscription = await (await registration()).pushManager.getSubscription();
  if (!browserSubscription || Notification.permission !== 'granted') {
    return { kind: 'revoked' };
  }
  if (browserSubscription.endpoint !== stored.endpoint) {
    // The browser rotated the subscription: register the new endpoint (re-registration rotates the token).
    await request(`/subscriptions/${stored.subscriptionId}`, { method: 'DELETE', token: stored.token }).catch(() => undefined);
    const renewed = await registerWithBackend(browserSubscription, stored.minSeverity);
    return { kind: 'on', subscriptionId: renewed.subscriptionId, minSeverity: renewed.minSeverity };
  }
  return { kind: 'on', subscriptionId: stored.subscriptionId, minSeverity: stored.minSeverity };
}

/** Must be called from a user gesture (button click). */
export async function enablePush(minSeverity: Severity = 'high'): Promise<PushState> {
  const availability = pushAvailability();
  if (availability !== 'supported') return { kind: 'unavailable', reason: availability };
  const config = await getPushConfig();
  if (!config.push_available || !config.vapid_public_key) return { kind: 'unavailable', reason: 'server-not-configured' };
  const permission = await Notification.requestPermission();
  if (permission === 'denied') return { kind: 'denied' };
  if (permission !== 'granted') return { kind: 'off' };
  const pushManager = (await registration()).pushManager;
  let subscription = await pushManager.getSubscription();
  if (!subscription) {
    subscription = await pushManager.subscribe({ userVisibleOnly: true,
      applicationServerKey: urlBase64ToUint8Array(config.vapid_public_key) as BufferSource });
  }
  const stored = await registerWithBackend(subscription, minSeverity);
  return { kind: 'on', subscriptionId: stored.subscriptionId, minSeverity };
}

/** Whether this device has registered a push subscription with the backend. */
export function hasPushSubscription(): boolean {
  return readStored() !== null;
}

export async function disablePush(): Promise<PushState> {
  const stored = readStored();
  if (pushAvailability() === 'supported') {
    const subscription = await (await registration()).pushManager.getSubscription().catch(() => null);
    await subscription?.unsubscribe().catch(() => false);
  }
  if (stored) await request(`/subscriptions/${stored.subscriptionId}`, { method: 'DELETE', token: stored.token }).catch(() => undefined);
  writeStored(null);
  return { kind: 'off' };
}

export async function setMinSeverity(minSeverity: Severity): Promise<void> {
  const stored = readStored();
  if (!stored) return;
  await request(`/subscriptions/${stored.subscriptionId}`, { method: 'PATCH', token: stored.token, json: { min_severity: minSeverity } });
  writeStored({ ...stored, minSeverity });
}

export async function sendTestPush(): Promise<PushDelivery> {
  const stored = readStored();
  if (!stored) throw new Error('Notifications are not enabled on this device');
  return (await request<{ delivery: PushDelivery }>(`/subscriptions/${stored.subscriptionId}/test`, { method: 'POST', token: stored.token })).delivery;
}

export async function getPushStatus(): Promise<{ status: string; deliveries: PushDelivery[] } | null> {
  const stored = readStored();
  if (!stored) return null;
  const body = await request<{ subscription: { status: string }; deliveries: PushDelivery[] }>(
    `/subscriptions/${stored.subscriptionId}`, { token: stored.token });
  return { status: body.subscription.status, deliveries: body.deliveries };
}
