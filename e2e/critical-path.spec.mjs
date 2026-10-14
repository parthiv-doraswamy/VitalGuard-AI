import { expect, test } from '@playwright/test';

const routes = [
  { path: '/#/dashboard', heading: 'Patient Monitoring Overview' },
  { path: '/#/patients', heading: 'Patients' },
  { path: '/#/alerts', heading: 'Alerts' },
  { path: '/#/analytics', heading: 'Analytics' },
  { path: '/#/settings', heading: 'Settings' },
];

// Protected workspaces correctly redirect unauthenticated visitors to /login.
// Sign in through the same documented demo flow a reviewer uses in the UI.
async function signInAsDemoAdmin(page) {
  await page.goto('/#/login');
  await page.getByRole('button', { name: /Admin/ }).click();
  await page.getByRole('button', { name: 'Open demo workspace' }).click();
  await expect(page).toHaveURL(/#\/dashboard$/);
}

test('all primary routes render and survive a browser reload', async ({ page }) => {
  await signInAsDemoAdmin(page);

  for (const route of routes) {
    await page.goto(route.path);
    const expectedUrl = new URL(route.path, process.env.E2E_BASE_URL || 'http://127.0.0.1:4173').toString();
    await expect(page).toHaveURL(expectedUrl);
    await expect(page.locator('#main-content')).toBeVisible();
    await expect(page.locator('#main-content').getByRole('heading', { name: route.heading, exact: true }).first()).toBeVisible();

    await page.reload();
    await expect(page).toHaveURL(expectedUrl);
    await expect(page.locator('#main-content')).toBeVisible();
    await expect(page.locator('#main-content').getByRole('heading', { name: route.heading, exact: true }).first()).toBeVisible();
  }
});

test('primary navigation moves between core workspaces', async ({ page }) => {
  await signInAsDemoAdmin(page);
  const navigation = page.getByRole('navigation', { name: 'Primary' });

  for (const route of routes.slice(1)) {
    await navigation.getByRole('link', { name: route.heading, exact: false }).click();
    await expect(page.locator('#main-content').getByRole('heading', { name: route.heading, exact: true }).first()).toBeVisible();
  }
});

test('mobile navigation opens and routes to Settings', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 });
  await signInAsDemoAdmin(page);
  await page.getByRole('button', { name: 'Open navigation menu' }).click();
  await page.getByRole('navigation', { name: 'Primary' }).getByRole('link', { name: 'Settings', exact: false }).click();
  await expect(page.locator('#main-content').getByRole('heading', { name: 'Settings', exact: true }).first()).toBeVisible();
});
