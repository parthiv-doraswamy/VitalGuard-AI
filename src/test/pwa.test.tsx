import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, fireEvent, render, screen } from '@testing-library/react';

const registerSW = vi.fn();
vi.mock('virtual:pwa-register', () => ({ registerSW: (options: unknown) => registerSW(options) }));

import { __resetPwaForTests, initPwa } from '../services/pwa.ts';
import { ConnectionBanner, UpdatePrompt } from '../components/layout/PwaStatus.tsx';
import { RiskEnginePanel } from '../components/settings/RiskEnginePanel.tsx';

import manifestSource from '../../public/manifest.webmanifest?raw';
import indexHtml from '../../index.html?raw';

const manifest = JSON.parse(manifestSource);
// Pixel sizes are verified on the built output by scripts/verify-pwa.mjs; here we check the files exist.
const iconFiles = Object.keys(import.meta.glob('../../public/icons/*.png')).map((path) => path.replace('../../public', ''));

function setOnline(online: boolean) {
  Object.defineProperty(window.navigator, 'onLine', { configurable: true, get: () => online });
  act(() => { window.dispatchEvent(new Event(online ? 'online' : 'offline')); });
}

beforeEach(() => {
  __resetPwaForTests();
  registerSW.mockReset();
  Object.defineProperty(window.navigator, 'serviceWorker', { configurable: true, value: {} });
});

afterEach(() => {
  setOnline(true);
  vi.restoreAllMocks();
});

describe('web app manifest', () => {
  it('has the fields browsers need to offer installation in standalone mode', () => {
    expect(manifest.name).toMatch(/VitalGuard/);
    expect(manifest.short_name.length).toBeLessThanOrEqual(12);
    expect(manifest.display).toBe('standalone');
    expect(manifest.start_url.startsWith(manifest.scope)).toBe(true);
    expect(manifest.id).toBe('/');
    expect(manifest.theme_color).toMatch(/^#[0-9a-f]{6}$/i);
    expect(manifest.background_color).toMatch(/^#[0-9a-f]{6}$/i);
    expect(manifest.description).toMatch(/Not for clinical use/);
  });

  it('declares 192 px, 512 px and maskable icons whose files exist', () => {
    const pngs = manifest.icons.filter((icon: { type: string }) => icon.type === 'image/png');
    for (const icon of pngs) expect(iconFiles).toContain(icon.src);
    const sizes = pngs.map((icon: { sizes: string }) => icon.sizes);
    expect(sizes).toEqual(expect.arrayContaining(['192x192', '512x512']));
    expect(pngs.some((icon: { purpose: string }) => icon.purpose === 'maskable')).toBe(true);
  });

  it('is linked from index.html with platform meta tags', () => {
    const html = indexHtml;
    expect(html).toContain('<link rel="manifest" href="/manifest.webmanifest" />');
    expect(html).toContain('name="theme-color"');
    expect(html).toContain('rel="apple-touch-icon" href="/icons/apple-touch-icon-180.png"');
    expect(html).toContain('viewport-fit=cover');
    expect(iconFiles).toContain('/icons/apple-touch-icon-180.png');
  });
});

describe('service worker registration and updates', () => {
  it('registers exactly one service worker no matter how often init runs', () => {
    registerSW.mockReturnValue(vi.fn());
    expect(initPwa()).toBe(true);
    expect(initPwa()).toBe(false);
    expect(registerSW).toHaveBeenCalledTimes(1);
  });

  it('does nothing where service workers are unsupported', () => {
    // @ts-expect-error simulate a browser without service workers
    delete window.navigator.serviceWorker;
    expect(initPwa()).toBe(false);
    expect(registerSW).not.toHaveBeenCalled();
  });

  it('asks before switching versions and only updates on confirmation', async () => {
    const updateSW = vi.fn().mockResolvedValue(undefined);
    let callbacks: { onNeedRefresh: () => void } = { onNeedRefresh: () => undefined };
    registerSW.mockImplementation((options) => { callbacks = options; return updateSW; });
    initPwa();
    render(<UpdatePrompt />);
    expect(screen.queryByTestId('update-prompt')).toBeNull();

    act(() => callbacks.onNeedRefresh());
    expect(screen.getByTestId('update-prompt')).toHaveTextContent('A new version is available');
    expect(updateSW).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: 'Later' }));
    expect(screen.queryByTestId('update-prompt')).toBeNull();

    act(() => callbacks.onNeedRefresh());
    await act(async () => { fireEvent.click(screen.getByRole('button', { name: /Update now/ })); });
    expect(updateSW).toHaveBeenCalledWith(true);
  });

  it('announces offline readiness honestly (app shell only)', () => {
    let callbacks: { onOfflineReady: () => void } = { onOfflineReady: () => undefined };
    registerSW.mockImplementation((options) => { callbacks = options; return vi.fn(); });
    initPwa();
    render(<UpdatePrompt />);
    act(() => callbacks.onOfflineReady());
    expect(screen.getByTestId('offline-ready')).toHaveTextContent('patient data and predictions still need the backend');
  });
});

describe('offline and stale data', () => {
  it('warns when offline and dates the last live backend data', () => {
    render(<ConnectionBanner liveStatus="reconnecting" lastLiveEventAt={new Date('2026-10-14T10:15:30').getTime()} />);
    setOnline(false);
    expect(screen.getByTestId('offline-banner')).toHaveTextContent('You are offline.');
    expect(screen.getByTestId('offline-banner')).toHaveTextContent('not served from cache');
    expect(screen.getByTestId('stale-since')).toHaveTextContent(/may be out of date/);
  });

  it('marks backend data as possibly stale while reconnecting, and hides when live', () => {
    const view = render(<ConnectionBanner liveStatus="reconnecting" lastLiveEventAt={null} />);
    expect(screen.getByTestId('stale-banner')).toHaveTextContent('Reconnecting to the backend');
    view.rerender(<ConnectionBanner liveStatus="offline" lastLiveEventAt={Date.now()} />);
    expect(screen.getByTestId('stale-banner')).toHaveTextContent('Backend unreachable.');
    view.rerender(<ConnectionBanner liveStatus="connected" lastLiveEventAt={Date.now()} />);
    expect(screen.queryByTestId('stale-banner')).toBeNull();
    expect(screen.queryByTestId('offline-banner')).toBeNull();
  });

  it('disables backend predictions offline instead of showing cached results', () => {
    render(<RiskEnginePanel />);
    expect(screen.getByRole('button', { name: /Run demo prediction/ })).toBeEnabled();
    setOnline(false);
    expect(screen.getByRole('button', { name: /Run demo prediction/ })).toBeDisabled();
    expect(screen.getByTestId('prediction-offline')).toHaveTextContent('unavailable offline');
    setOnline(true);
    expect(screen.getByRole('button', { name: /Run demo prediction/ })).toBeEnabled();
  });
});
