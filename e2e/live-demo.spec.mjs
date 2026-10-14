import { expect, test } from '@playwright/test';

// Two-device synchronized streaming test. Needs a running backend and a frontend
// build pointed at it (VITE_API_BASE_URL); see docs/REALTIME_DEMO_ROADMAP.md.
// Every record it creates is fictional demo data.
const apiUrl = process.env.E2E_LIVE_API_URL;
test.skip(!apiUrl, 'E2E_LIVE_API_URL is not set; synchronized streaming needs a live backend.');
test.describe.configure({ mode: 'serial' });
test.setTimeout(120_000);

async function signIn(page) {
  await page.goto('/#/login');
  await page.getByRole('button', { name: /Admin/ }).click();
  await page.getByRole('button', { name: 'Open demo workspace' }).click();
  await expect(page).toHaveURL(/#\/dashboard$/);
}

async function startStream(producer, scenario) {
  await producer.getByLabel('Stream scenario').selectOption(scenario);
  await producer.getByLabel('Stream interval').selectOption('1000');
  await producer.getByRole('button', { name: 'Start stream' }).click();
  const takeover = producer.getByRole('button', { name: 'Take over and start' });
  // A stream left over from an earlier run is replaced explicitly, never silently.
  if (await takeover.isVisible({ timeout: 1500 }).catch(() => false)) await takeover.click();
  await expect(producer.getByTestId('producer-phase')).toHaveText('running');
}

const text = async (page, testId) => (await page.getByTestId(testId).first().textContent())?.trim();
const eventNumber = async (page, testId) => Number((await text(page, testId))?.replace('#', ''));

async function backendEvents(request, sessionId) {
  const response = await request.get(`${apiUrl}/api/v1/observations`, { params: { session_id: sessionId, after_id: 0, limit: 100 } });
  expect(response.ok()).toBeTruthy();
  return (await response.json()).items;
}

test('Laptop B mirrors the backend stream started on Laptop A, including pause, reconnect and stop', async ({ browser, request }) => {
  const laptopA = await browser.newContext();
  const laptopB = await browser.newContext();
  const producer = await laptopA.newPage();
  const receiver = await laptopB.newPage();

  // Laptop B's live socket can be cut and restored while its REST calls keep working.
  let receiverBlocked = false;
  const receiverSockets = [];
  await receiver.routeWebSocket(/\/api\/v1\/live$/, (ws) => {
    if (receiverBlocked) { ws.close(); return; }
    ws.connectToServer();
    receiverSockets.push(ws);
  });

  await signIn(receiver);
  await expect(receiver.getByTestId('live-connection-status')).toHaveText('connected');
  await signIn(producer);
  await producer.goto('/#/live-demo');
  await expect(producer.getByTestId('live-connection-status')).toHaveText('connected');

  // Laptop B has no producer controls; it only receives.
  await expect(receiver.getByRole('button', { name: 'Start stream' })).toHaveCount(0);

  await startStream(producer, 'worsening');
  await expect(receiver.getByTestId('live-session-status')).toHaveText('Streaming');
  const sessionShort = await text(producer, 'live-session-id');
  await expect(receiver.getByTestId('live-session-id')).toHaveText(sessionShort);

  // Same event, same values on both laptops, without refreshing Laptop B.
  await expect.poll(() => eventNumber(receiver, 'live-latest-event-id')).toBeGreaterThan(0);
  const shared = await eventNumber(receiver, 'live-latest-event-id');
  const producerRow = producer.locator(`[data-testid="live-log-row"][data-event-id="${shared}"]`);
  await expect(producerRow).toHaveCount(1);
  await expect(producerRow).toContainText(`#${shared}`);
  const receiverScore = await text(receiver, 'live-latest-score');
  await expect(producerRow).toContainText(receiverScore);

  const sessionId = (await (await request.get(`${apiUrl}/api/v1/live-demo/sessions/current`)).json()).session.session_id;
  expect(sessionId.startsWith(sessionShort)).toBeTruthy();
  const committed = (await backendEvents(request, sessionId)).find((item) => item.id === shared);
  expect(String(committed.prediction.risk_score)).toBe(receiverScore);
  await expect(receiver.getByTestId('live-latest-model')).toHaveText(committed.model_version);
  await expect(receiver.getByTestId('live-latency-last')).toHaveText(/≈\d+ ms/);

  // Pause: Laptop B sees the state change and no new events arrive.
  await producer.getByRole('button', { name: 'Pause' }).click();
  await expect(receiver.getByTestId('live-session-status')).toHaveText('Paused by producer');
  const pausedCount = await text(receiver, 'live-events-received');
  await receiver.waitForTimeout(2500);
  expect(await text(receiver, 'live-events-received')).toBe(pausedCount);
  await producer.getByRole('button', { name: 'Resume' }).click();
  await expect(receiver.getByTestId('live-session-status')).toHaveText('Streaming');
  await expect.poll(async () => Number(await text(receiver, 'live-events-received'))).toBeGreaterThan(Number(pausedCount));

  // Disconnect Laptop B while Laptop A keeps streaming, then reconnect.
  receiverBlocked = true;
  for (const ws of receiverSockets.splice(0)) await ws.close();
  await expect(receiver.getByTestId('live-connection-status')).not.toHaveText('connected');
  const beforeGap = await eventNumber(producer, 'producer-last-event-id');
  await expect.poll(() => eventNumber(producer, 'producer-last-event-id'), { timeout: 15_000 }).toBeGreaterThanOrEqual(beforeGap + 3);
  receiverBlocked = false;
  await expect(receiver.getByTestId('live-connection-status')).toHaveText('connected', { timeout: 40_000 });
  await expect.poll(async () => Number(await text(receiver, 'live-events-recovered')), { timeout: 15_000 }).toBeGreaterThanOrEqual(3);

  // Stop: Laptop B stays a receiver and shows the stopped stream.
  await producer.getByRole('button', { name: 'Stop stream' }).click();
  await expect(producer.getByTestId('producer-phase')).toHaveText('stopped');
  await expect(receiver.getByTestId('live-session-status')).toHaveText('Stopped (producer stopped)');
  await expect(receiver.getByTestId('live-connection-status')).toHaveText('connected');
  const finalId = await eventNumber(producer, 'producer-last-event-id');
  await expect.poll(() => eventNumber(receiver, 'live-latest-event-id')).toBe(finalId);

  // Reconnect and catch-up created no duplicate records: one row per sequence, no gaps.
  const records = await backendEvents(request, sessionId);
  const sequences = records.map((item) => item.sequence);
  expect(sequences).toEqual([...Array(records.length).keys()]);
  expect(new Set(records.map((item) => item.id)).size).toBe(records.length);
  expect(Number(await text(receiver, 'live-events-received'))).toBeGreaterThanOrEqual(records.length);
  const alertsResponse = await request.get(`${apiUrl}/api/v1/alerts`, { params: { patient_id: records[0].patient_id, limit: 100 } });
  const alertObservationIds = (await alertsResponse.json()).items.map((alert) => alert.details.observation_id);
  expect(new Set(alertObservationIds).size).toBe(alertObservationIds.length);

  // A stable scenario streams through the same path.
  await producer.getByRole('button', { name: 'New stream' }).click();
  await startStream(producer, 'stable');
  await expect(receiver.getByTestId('live-session-status')).toHaveText('Streaming');
  await expect.poll(async () => (await text(receiver, 'live-session-id')) !== sessionShort).toBeTruthy();
  await expect.poll(() => eventNumber(receiver, 'live-latest-event-id')).toBeGreaterThan(finalId);
  await expect(receiver.getByTestId('live-latest-alert')).toHaveCount(0);
  await producer.getByRole('button', { name: 'Stop stream' }).click();
  await expect(receiver.getByTestId('live-session-status')).toHaveText('Stopped (producer stopped)');

  await laptopA.close();
  await laptopB.close();
});

test('a second producer is refused until it explicitly takes over', async ({ browser }) => {
  const first = await (await browser.newContext()).newPage();
  const second = await (await browser.newContext()).newPage();
  await signIn(first);
  await first.goto('/#/live-demo');
  await startStream(first, 'stable');

  await signIn(second);
  await second.goto('/#/live-demo');
  await second.getByRole('button', { name: 'Start stream' }).click();
  await expect(second.getByText('Another producer is already streaming.')).toBeVisible();
  await expect(first.getByTestId('producer-phase')).toHaveText('running');

  await second.getByRole('button', { name: 'Take over and start' }).click();
  await expect(second.getByTestId('producer-phase')).toHaveText('running');
  // The first producer learns on its next request that it no longer owns an active stream.
  await expect(first.getByTestId('producer-phase')).toHaveText('stopped', { timeout: 10_000 });
  await second.getByRole('button', { name: 'Stop stream' }).click();
});
