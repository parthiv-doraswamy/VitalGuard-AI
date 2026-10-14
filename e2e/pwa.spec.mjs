import { expect, test } from '@playwright/test';

// Chromium only. Runs against the local production preview; against a deployed URL it
// runs only when E2E_PWA=1 (that deployment must already include the service worker).
test.skip(Boolean(process.env.E2E_BASE_URL) && !process.env.E2E_PWA, 'PWA checks need a build that ships the service worker');
test.describe.configure({ mode: 'serial' });

async function signIn(page) {
  await page.goto('/#/login');
  await page.getByRole('button', { name: /Admin/ }).click();
  await page.getByRole('button', { name: 'Open demo workspace' }).click();
  await expect(page).toHaveURL(/#\/dashboard$/);
}

async function waitForController(page) {
  await page.evaluate(() => navigator.serviceWorker.ready);
  if (!(await page.evaluate(() => Boolean(navigator.serviceWorker.controller)))) await page.reload();
  await expect.poll(() => page.evaluate(() => Boolean(navigator.serviceWorker.controller))).toBe(true);
}

async function cachedUrls(page) {
  return page.evaluate(async () => {
    const urls = [];
    for (const name of await caches.keys()) {
      const cache = await caches.open(name);
      for (const request of await cache.keys()) urls.push(`${name} ${request.url}`);
    }
    return urls;
  });
}

test('manifest is valid and Chromium reports the app as installable', async ({ page, request }) => {
  const manifest = await request.get('/manifest.webmanifest');
  expect(manifest.ok()).toBeTruthy();
  expect((await manifest.json()).display).toBe('standalone');
  await page.goto('/');
  await waitForController(page);
  const cdp = await page.context().newCDPSession(page);
  const { installabilityErrors } = await cdp.send('Page.getInstallabilityErrors');
  expect(installabilityErrors).toEqual([]);
  const { url, data, errors } = await cdp.send('Page.getAppManifest');
  expect(url).toMatch(/manifest\.webmanifest$/);
  expect(errors).toEqual([]);
  expect(JSON.parse(data).start_url).toBe('/?source=pwa');
});

test('exactly one service worker is registered and it controls the page', async ({ page }) => {
  await page.goto('/');
  await waitForController(page);
  const registrations = await page.evaluate(async () => (await navigator.serviceWorker.getRegistrations())
    .map((registration) => registration.active?.scriptURL));
  expect(registrations).toHaveLength(1);
  expect(registrations[0]).toMatch(/\/sw\.js$/);
});

test('offline: app shell and protected routes still load, live data is marked unavailable', async ({ page, context }) => {
  await signIn(page);
  await waitForController(page);
  await context.setOffline(true);
  try {
    await page.reload();
    await expect(page.locator('#main-content').getByRole('heading', { name: 'Patient Monitoring Overview' })).toBeVisible();
    await expect(page.getByTestId('offline-banner')).toContainText('You are offline.');
    await page.goto('/#/settings');
    await expect(page.locator('#main-content').getByRole('heading', { name: 'Settings', exact: true }).first()).toBeVisible();
    await expect(page.getByRole('button', { name: /Run demo prediction/ })).toBeDisabled();
    await expect(page.getByTestId('prediction-offline')).toBeVisible();
  } finally {
    await context.setOffline(false);
  }
  await expect(page.getByTestId('offline-banner')).toHaveCount(0);
});

test('caches hold only the app shell, static assets and fonts — never API responses', async ({ page }) => {
  await signIn(page);
  await waitForController(page);
  // Visit pages that call the backend API (whether or not it is reachable).
  for (const route of ['/#/dashboard', '/#/alerts', '/#/settings', '/#/live-demo']) {
    await page.goto(route);
    await page.waitForTimeout(500);
  }
  const origin = new URL(page.url()).origin;
  const urls = await cachedUrls(page);
  expect(urls.length).toBeGreaterThan(5);
  for (const entry of urls) {
    const url = new URL(entry.split(' ')[1]);
    const allowed = (url.origin === origin && !url.pathname.startsWith('/api/'))
      || url.origin === 'https://fonts.googleapis.com' || url.origin === 'https://fonts.gstatic.com';
    expect(allowed, `unexpected cached URL ${entry}`).toBe(true);
  }
  expect(urls.some((entry) => /\/api\/v1\//.test(entry))).toBe(false);
});
