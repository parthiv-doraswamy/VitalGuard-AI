import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import pushWorkerSource from '../../public/push-sw.js?raw';
import { disablePush, enablePush, pushAvailability, reconcilePush, urlBase64ToUint8Array } from '../services/notifications.ts';
import { NotificationSettings } from '../components/settings/NotificationSettings.tsx';
import { AlertsPage } from '../pages/AlertsPage.tsx';
import { SimulationProvider } from '../store/SimulationContext.tsx';

const VAPID_KEY = 'BLx0' + 'A'.repeat(83);
const ENDPOINT = 'https://fcm.googleapis.com/fcm/send/abc';

// --- Fake browser push APIs ------------------------------------------------------------------
function installPushApis({ permission = 'default' as NotificationPermission, requestResult = 'granted' as NotificationPermission,
  existing = null as null | { endpoint: string } } = {}) {
  let current: (PushSubscription & { unsubscribe: ReturnType<typeof vi.fn> }) | null = existing ? makeSubscription(existing.endpoint) : null;
  const pushManager = {
    getSubscription: vi.fn(async () => current),
    subscribe: vi.fn(async () => { current = makeSubscription(ENDPOINT); return current; }),
  };
  Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: { ready: Promise.resolve({ pushManager }) } });
  vi.stubGlobal('PushManager', function PushManager() {});
  const NotificationMock = Object.assign(function Notification() {}, {
    permission,
    requestPermission: vi.fn(async () => { NotificationMock.permission = requestResult; return requestResult; }),
  });
  vi.stubGlobal('Notification', NotificationMock);
  Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
  return { pushManager, NotificationMock };
}

function makeSubscription(endpoint: string) {
  return {
    endpoint,
    toJSON: () => ({ endpoint, keys: { p256dh: 'B' + 'x'.repeat(86), auth: 'y'.repeat(22) } }),
    unsubscribe: vi.fn(async () => true),
  } as unknown as PushSubscription & { unsubscribe: ReturnType<typeof vi.fn> };
}

function mockApi(overrides: Record<string, (init?: RequestInit) => unknown> = {}) {
  const calls: Array<{ url: string; method: string; body: unknown; headers: Headers }> = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    calls.push({ url, method: init?.method ?? 'GET', body: init?.body ? JSON.parse(String(init.body)) : null,
      headers: new Headers(init?.headers) });
    const key = Object.keys(overrides).find((pattern) => url.includes(pattern));
    const body = key ? overrides[key](init) : url.endsWith('/config')
      ? { push_available: true, vapid_public_key: VAPID_KEY }
      : url.endsWith('/subscriptions') ? { subscription: { subscription_id: 'sub-1' }, management_token: 'tok-1' }
      : { items: [], count: 0, subscription: { status: 'active' }, deliveries: [] };
    const status = (init?.method === 'DELETE') ? 204 : 200;
    return { ok: true, status, json: async () => body } as Response;
  }));
  return calls;
}

beforeEach(() => { localStorage.clear(); });
afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  localStorage.clear();
});

// --- Service worker handlers (public/push-sw.js) --------------------------------------------
function loadWorker({ windows = [] as Array<{ url: string; postMessage: ReturnType<typeof vi.fn>; focus: ReturnType<typeof vi.fn> }> } = {}) {
  const listeners: Record<string, (event: unknown) => void> = {};
  const sw = {
    location: { origin: 'https://vitalguard-ai-g215.onrender.com' },
    addEventListener: (type: string, listener: (event: unknown) => void) => { listeners[type] = listener; },
    registration: { showNotification: vi.fn(async () => undefined) },
    clients: { matchAll: vi.fn(async () => windows), openWindow: vi.fn(async () => null) },
    vgPush: undefined as unknown as { safeUrl: (url: unknown) => string; parsePayload: (text: string) => unknown;
      notificationFor: (payload: unknown) => { title: string; options: NotificationOptions & { data: Record<string, unknown> } } },
  };
  new Function('self', pushWorkerSource)(sw);
  return { sw, listeners };
}

const ALERT_PAYLOAD = { v: 1, type: 'alert', alert_id: 42, severity: 'critical', title: 'VitalGuard: critical demo alert',
  body: 'A new synthetic demo alert needs review. Open VitalGuard to see it.', url: '/#/alerts?alert=42', tag: 'vg-alert-42',
  delivery_id: 7, receipt: { url: 'https://vitalguard-risk-api.onrender.com/api/v1/notifications/receipts', nonce: 'n'.repeat(32) } };

describe('service worker push handlers', () => {
  it('shows a lock-screen safe notification and reports it as displayed', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    const { sw, listeners } = loadWorker();
    let done: Promise<unknown> = Promise.resolve();
    listeners.push({ data: { text: () => JSON.stringify(ALERT_PAYLOAD) }, waitUntil: (promise: Promise<unknown>) => { done = promise; } });
    await done;
    const [title, options] = sw.registration.showNotification.mock.calls[0] as unknown as [string, NotificationOptions & { data: Record<string, unknown> }];
    expect(title).toBe('VitalGuard: critical demo alert');
    expect(options.requireInteraction).toBe(true);
    expect(options.tag).toBe('vg-alert-42');
    expect(options.data.url).toBe('/#/alerts?alert=42');
    expect(JSON.stringify(options)).not.toMatch(/patient|DEMO-|heart_rate|spo2/i);
    const [url, init] = fetchMock.mock.calls[0] as unknown as [string, RequestInit];
    expect(url).toBe(ALERT_PAYLOAD.receipt.url);
    expect(JSON.parse(String(init.body))).toEqual({ delivery_id: 7, nonce: 'n'.repeat(32), event: 'displayed' });
  });

  it('falls back to a generic notification for malformed or foreign payloads', () => {
    const { sw } = loadWorker();
    for (const text of ['not json', JSON.stringify({ v: 2, type: 'alert' }), JSON.stringify({ v: 1, type: 'exec' })]) {
      expect(sw.vgPush.parsePayload(text)).toBeNull();
    }
    const generic = sw.vgPush.notificationFor(null);
    expect(generic.title).toBe('VitalGuard');
    expect(generic.options.data.url).toBe('/#/alerts');
  });

  it.each([
    ['https://evil.example.org', '/#/alerts'],
    ['//evil.example.org/#/alerts', '/#/alerts'],
    ['/#/alerts?alert=1"><script>', '/#/alerts'],
    ['javascript:alert(1)', '/#/alerts'],
    ['/#/admin', '/#/alerts'],
    ['/#/alerts?alert=12', '/#/alerts?alert=12'],
    ['/#/settings', '/#/settings'],
  ])('only routes to this app (%s)', (input, expected) => {
    expect(loadWorker().sw.vgPush.safeUrl(input)).toBe(expected);
  });

  it('routes an open window in place, or opens a new one, then reports the click', async () => {
    const fetchMock = vi.fn(async () => ({ ok: true }));
    vi.stubGlobal('fetch', fetchMock);
    const client = { url: 'https://vitalguard-ai-g215.onrender.com/#/dashboard', postMessage: vi.fn(), focus: vi.fn(async () => client) };
    const open = loadWorker({ windows: [client] });
    const notification = { close: vi.fn(), data: open.sw.vgPush.notificationFor(ALERT_PAYLOAD).options.data };
    let done: Promise<unknown> = Promise.resolve();
    open.listeners.notificationclick({ notification, waitUntil: (promise: Promise<unknown>) => { done = promise; } });
    await done;
    expect(notification.close).toHaveBeenCalled();
    expect(client.postMessage).toHaveBeenCalledWith({ type: 'vg-navigate', url: '/#/alerts?alert=42' });
    expect(client.focus).toHaveBeenCalled();
    expect(JSON.parse(String((fetchMock.mock.calls[0] as unknown as [string, RequestInit])[1].body)).event).toBe('clicked');

    const closed = loadWorker();
    closed.listeners.notificationclick({ notification: { close: vi.fn(), data: { url: '/#/alerts?alert=42' } },
      waitUntil: (promise: Promise<unknown>) => { done = promise; } });
    await done;
    expect(closed.sw.clients.openWindow).toHaveBeenCalledWith('https://vitalguard-ai-g215.onrender.com/#/alerts?alert=42');
  });
});

// --- Client subscription management -------------------------------------------------------------
describe('notification opt-in', () => {
  it('reports unsupported browsers and iOS Safari outside the installed app', () => {
    Object.defineProperty(window, 'isSecureContext', { configurable: true, value: true });
    Object.defineProperty(navigator, 'serviceWorker', { configurable: true, value: undefined });
    expect(pushAvailability()).toBe('unsupported');
    vi.spyOn(navigator, 'userAgent', 'get').mockReturnValue('Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X)');
    expect(pushAvailability()).toBe('needs-install');
  });

  it('does not prompt for permission when the server has no push configuration', async () => {
    const { NotificationMock } = installPushApis();
    mockApi({ '/config': () => ({ push_available: false, vapid_public_key: null }) });
    expect(await enablePush()).toEqual({ kind: 'unavailable', reason: 'server-not-configured' });
    expect(NotificationMock.requestPermission).not.toHaveBeenCalled();
  });

  it('respects a denied permission without subscribing', async () => {
    const { pushManager } = installPushApis({ requestResult: 'denied' });
    const calls = mockApi();
    expect(await enablePush()).toEqual({ kind: 'denied' });
    expect(pushManager.subscribe).not.toHaveBeenCalled();
    expect(calls.some((call) => call.url.endsWith('/subscriptions'))).toBe(false);
  });

  it('subscribes with the server key and registers the subscription when granted', async () => {
    const { pushManager } = installPushApis();
    const calls = mockApi();
    expect(await enablePush('critical')).toEqual({ kind: 'on', subscriptionId: 'sub-1', minSeverity: 'critical' });
    const options = (pushManager.subscribe.mock.calls[0] as unknown as [PushSubscriptionOptionsInit])[0];
    expect(options.userVisibleOnly).toBe(true);
    expect(Array.from(options.applicationServerKey as Uint8Array)).toEqual(Array.from(urlBase64ToUint8Array(VAPID_KEY)));
    const registration = calls.find((call) => call.url.endsWith('/subscriptions'))!;
    expect(registration.body).toMatchObject({ subscription: { endpoint: ENDPOINT }, min_severity: 'critical' });
    expect(JSON.parse(localStorage.getItem('vg-push-subscription')!)).toMatchObject({ subscriptionId: 'sub-1', token: 'tok-1' });
  });

  it('survives reload, detects revocation and removes server-side state when permission is denied', async () => {
    localStorage.setItem('vg-push-subscription', JSON.stringify({ subscriptionId: 'sub-1', token: 'tok-1', endpoint: ENDPOINT, minSeverity: 'high' }));
    installPushApis({ permission: 'granted', existing: { endpoint: ENDPOINT } });
    mockApi();
    expect(await reconcilePush()).toEqual({ kind: 'on', subscriptionId: 'sub-1', minSeverity: 'high' });

    installPushApis({ permission: 'granted', existing: null });
    expect(await reconcilePush()).toEqual({ kind: 'revoked' });

    installPushApis({ permission: 'denied' });
    const calls = mockApi();
    expect(await reconcilePush()).toEqual({ kind: 'denied' });
    const deletion = calls.find((call) => call.method === 'DELETE')!;
    expect(deletion.url).toMatch(/\/subscriptions\/sub-1$/);
    expect(deletion.headers.get('X-Subscription-Token')).toBe('tok-1');
    expect(localStorage.getItem('vg-push-subscription')).toBeNull();
  });

  it('re-registers when the browser rotated its subscription', async () => {
    localStorage.setItem('vg-push-subscription', JSON.stringify({ subscriptionId: 'old', token: 'tok-old', endpoint: 'https://fcm.googleapis.com/old', minSeverity: 'high' }));
    installPushApis({ permission: 'granted', existing: { endpoint: ENDPOINT } });
    const calls = mockApi();
    expect(await reconcilePush()).toEqual({ kind: 'on', subscriptionId: 'sub-1', minSeverity: 'high' });
    expect(calls.find((call) => call.method === 'DELETE')?.url).toMatch(/\/subscriptions\/old$/);
    expect(calls.find((call) => call.url.endsWith('/subscriptions'))?.body).toMatchObject({ subscription: { endpoint: ENDPOINT } });
  });

  it('turning off unsubscribes the browser and deletes the server subscription', async () => {
    localStorage.setItem('vg-push-subscription', JSON.stringify({ subscriptionId: 'sub-1', token: 'tok-1', endpoint: ENDPOINT, minSeverity: 'high' }));
    const { pushManager } = installPushApis({ permission: 'granted', existing: { endpoint: ENDPOINT } });
    const calls = mockApi();
    const subscription = await pushManager.getSubscription();
    expect(await disablePush()).toEqual({ kind: 'off' });
    expect(subscription!.unsubscribe).toHaveBeenCalled();
    expect(calls.some((call) => call.method === 'DELETE')).toBe(true);
    expect(localStorage.getItem('vg-push-subscription')).toBeNull();
  });
});

// --- UI -----------------------------------------------------------------------------------------
describe('notification UI', () => {
  it('explains a denied permission without blocking anything', async () => {
    installPushApis({ permission: 'denied' });
    mockApi();
    render(<SimulationProvider><MemoryRouter><NotificationSettings /></MemoryRouter></SimulationProvider>);
    expect(await screen.findByText(/Notifications are blocked for this site/)).toBeInTheDocument();
    expect(screen.getByText(/In-app alerts still work/)).toBeInTheDocument();
  });

  it('enables notifications only after an explicit click', async () => {
    const { NotificationMock } = installPushApis();
    mockApi();
    render(<SimulationProvider><MemoryRouter><NotificationSettings /></MemoryRouter></SimulationProvider>);
    const button = await screen.findByRole('button', { name: /Enable notifications on this device/ });
    expect(NotificationMock.requestPermission).not.toHaveBeenCalled();
    fireEvent.click(button);
    expect(await screen.findByText('Notifications are on for this device.')).toBeInTheDocument();
    expect(screen.getByLabelText('Minimum alert severity')).toHaveValue('high');
    expect(NotificationMock.requestPermission).toHaveBeenCalledTimes(1);
  });

  it('highlights the alert opened from a notification and points to the in-app fallback', async () => {
    installPushApis({ permission: 'default' });
    mockApi({ '/api/v1/alerts?limit=100': () => ({ items: [
      { id: 41, patient_id: 'DEMO-1', severity: 'high', status: 'open', title: 'High demo risk score', created_at: '2026-10-14T10:00:00Z', details: {} },
      { id: 42, patient_id: 'DEMO-2', severity: 'critical', status: 'open', title: 'Critical demo risk score', created_at: '2026-10-14T10:01:00Z', details: {} },
    ], count: 2 }) });
    Element.prototype.scrollIntoView = vi.fn();
    const { container } = render(
      <SimulationProvider><MemoryRouter initialEntries={['/alerts?alert=42']}>
        <Routes><Route path="/alerts" element={<AlertsPage />} /></Routes>
      </MemoryRouter></SimulationProvider>,
    );
    await waitFor(() => expect(container.querySelector('#backend-alert-42')).not.toBeNull());
    expect(container.querySelector('#backend-alert-42')).toHaveAttribute('data-highlighted', 'true');
    expect(container.querySelector('#backend-alert-41')).not.toHaveAttribute('data-highlighted');
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled();
    expect(await screen.findByTestId('push-fallback')).toHaveTextContent('New backend alerts appear here');
  });
});
