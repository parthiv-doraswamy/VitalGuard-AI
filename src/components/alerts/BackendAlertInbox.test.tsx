import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render, screen, waitFor } from '@testing-library/react';
import { BackendAlertInbox } from './BackendAlertInbox.tsx';

vi.mock('../../services/useLiveEvents.ts', () => ({
  useLiveEvents: () => ({ alertsReceived: 0, status: 'connected' }),
}));
vi.mock('../../services/pwa.ts', () => ({
  useOnlineStatus: () => true,
}));

function jsonResponse(body: unknown, ok = true, status = 200): Response {
  return { ok, status, json: async () => body } as Response;
}

describe('BackendAlertInbox Phase 13 review preview', () => {
  beforeEach(() => {
    sessionStorage.clear();
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(jsonResponse({ items: [], count: 0, demo_only: true })));
  });

  afterEach(() => {
    cleanup();
    vi.unstubAllGlobals();
  });

  it('keeps the inbox available and explains missing preview credentials', async () => {
    render(<BackendAlertInbox />);

    expect(await screen.findByText(/Review deadline preview needs a valid backend escalation bearer token/i)).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Alert operations inbox' })).toBeTruthy();
    expect(fetch).toHaveBeenCalledTimes(1);
  });

  it('keeps alerts visible when the protected preview returns 503', async () => {
    sessionStorage.setItem('vitalguard.operator.session', JSON.stringify({
      token: 'test-token',
      expiresAt: Date.now() + 60_000,
    }));
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ items: [], count: 0, demo_only: true }))
      .mockResolvedValueOnce(jsonResponse({ detail: 'not configured' }, false, 503));

    render(<BackendAlertInbox />);

    expect(await screen.findByText(/Review deadline preview is unavailable/i)).toBeTruthy();
    expect(screen.getByRole('heading', { name: 'Alert operations inbox' })).toBeTruthy();
    expect(new Headers(vi.mocked(fetch).mock.calls[1][1]?.headers).get('Authorization')).toBe('Bearer test-token');
  });

  it('renders the due count when the protected preview succeeds', async () => {
    sessionStorage.setItem('vitalguard.operator.session', JSON.stringify({
      token: 'test-token',
      expiresAt: Date.now() + 60_000,
    }));
    vi.mocked(fetch)
      .mockResolvedValueOnce(jsonResponse({ items: [], count: 0, demo_only: true }))
      .mockResolvedValueOnce(jsonResponse({
        items: [{ alert_id: 17, severity: 'high', deadline_minutes: 15, elapsed_minutes: 20, review_due: true, minutes_until_due: 0 }],
        count: 1,
        due_count: 1,
        policy_version: 'demo-escalation-policy-0.1.0',
        demo_only: true,
        notifications_sent: false,
        clinical_policy: false,
      }));

    render(<BackendAlertInbox />);

    expect(await screen.findByText('1 due for review')).toBeTruthy();
    await waitFor(() => expect(screen.getByText(/Alert #17 · high · overdue by 5 min/i)).toBeTruthy());
  });
});
