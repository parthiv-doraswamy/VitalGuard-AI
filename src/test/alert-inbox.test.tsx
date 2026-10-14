import { afterEach, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/react';
import { BackendAlertInbox } from '../components/alerts/BackendAlertInbox.tsx';

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
});

it('does not set Content-Type on alert list GET requests', async () => {
  const fetchMock = vi.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ items: [], count: 0, demo_only: true }),
  });
  vi.stubGlobal('fetch', fetchMock);
  const view = render(<BackendAlertInbox />);

  await waitFor(() => expect(fetchMock).toHaveBeenCalled());
  const call = fetchMock.mock.calls.find(([url]) => String(url).includes('/api/v1/alerts?limit=100'));
  expect(call).toBeTruthy();
  const init = call?.[1] as RequestInit;
  expect(new Headers(init.headers).has('Content-Type')).toBe(false);
  view.unmount();
});
