# Web Push notifications

> Synthetic demo alerts only. A notification is a prompt to open the app, not a
> clinical alarm: delivery is best effort and can be delayed, dropped or silenced
> by the browser, the operating system or the push service.

## Identity and ownership

The deployed backend has **no user accounts or roles** (the demo login is client-side; the unmerged `phase-4-authorization` branch has only a single-operator token). Subscriptions are therefore **device-scoped**:

- `POST /api/v1/notifications/subscriptions` returns a `management_token` once. Only its SHA-256 hash is stored. The browser keeps the token in `localStorage`.
- Reading status, changing preferences, sending a test or deleting requires `X-Subscription-Token`. A wrong or missing token returns 403.
- Re-registering the same endpoint (only the owning browser knows it) reactivates the subscription and **rotates** the token.
- **Not possible until real authentication exists:** targeting by user or role (for example "nurses on ward 3"), and listing a user's devices.

## Configuration (backend private environment only)

| Variable | Purpose |
| --- | --- |
| `VITALGUARD_VAPID_PRIVATE_KEY` | VAPID private key (base64url). Generate with `python backend/scripts/generate_vapid_keys.py`. **Never commit it.** The public key is derived and served from `/api/v1/notifications/config`. Rotating it invalidates all subscriptions. |
| `VITALGUARD_VAPID_SUBJECT` | `mailto:` or `https:` contact sent to push services |
| `VITALGUARD_PUBLIC_API_URL` | Public API base for service-worker receipts (defaults to the request URL) |
| `VITALGUARD_PUSH_MAX_SUBSCRIPTIONS` | Cap on active subscriptions (default 1000) |
| `VITALGUARD_PUSH_ALLOWED_HOSTS` | Override the push-service host allowlist (tests only) |
| `VITALGUARD_LOG_LEVEL` | App log level (default INFO), so delivery diagnostics are visible |

Without VAPID keys, push is reported as unavailable, nothing is queued, and the in-app alert center works unchanged.

## Delivery pipeline

1. **Enqueue in the alert's transaction.** `insert_alert` writes one `push_deliveries` row per eligible active subscription (severity at or above its `min_severity`, enabled) in the same transaction (migration v6). If the alert rolls back, nothing is queued. `(subscription_id, event_key)` is unique, so duplicate alerts, retries and multiple backend instances cannot send twice.
2. **Send after commit.** The push worker is woken when the committed `alert.created` event is dispatched, and also polls. It claims rows with a conditional UPDATE (one instance wins each row), encrypts the payload (aes128gcm), signs with VAPID and POSTs to the push service. Headers: `TTL: 3600`, `Urgency` (high for critical), and `Topic` (collapses repeats of the same alert at the push service).
3. **Outcomes:**

| Push service response | Recorded as | Action |
| --- | --- | --- |
| 201/202 | `accepted` | **Only means the push service took it**, not that the device received or showed it |
| 429, 5xx, network error | `retrying` | Exponential backoff (10 s → 15 min, honours `Retry-After`), up to 5 attempts, then `failed` |
| 404/410 | `expired` | Subscription deactivated; its other pending deliveries are `skipped`; no new deliveries |
| Other 4xx (e.g. 400, 413) | `failed` | Not retried |

4. **Device receipts.** The service worker posts `displayed` after `showNotification` resolves and `clicked` on click. The receipt is authenticated with an HMAC nonce in the encrypted payload. Only these set `displayed_at` / `clicked_at`. A missing receipt means unknown, not "not shown".

## Payload (what can appear on a lock screen)

```json
{"v":1,"type":"alert","alert_id":42,"severity":"critical","title":"VitalGuard: critical demo alert",
 "body":"A new synthetic demo alert needs review. Open VitalGuard to see it.",
 "url":"/#/alerts?alert=42","tag":"vg-alert-42","delivery_id":7,"receipt":{"url":"…/api/v1/notifications/receipts","nonce":"…"}}
```

It contains **no patient identifier, vitals, risk score or alert free text**, and it is encrypted end to end to the browser. Tests decrypt real payloads to check this.

## Security controls

- **SSRF guard:** endpoints must be HTTPS on a known push service (`fcm.googleapis.com`, Mozilla autopush, `*.push.apple.com`, `*.notify.windows.com`); credentials in the URL are rejected.
- Subscription keys are validated (65-byte P-256 point, 16-byte auth secret).
- Endpoints are capability URLs. They are stored but never returned by the API or written to logs; logs use subscription and delivery IDs only.
- Notification clicks only route to this app's own hash routes (`/#/alerts`, `/#/settings`, `/#/dashboard`, `/#/live-demo`).
- Unsubscribing deletes the endpoint, keys and delivery history.
- General caveat: uvicorn access logs include query strings, so API calls such as `GET /api/v1/alerts?patient_id=…` record the (synthetic) patient ID. This is not part of the push path, but it matters if real identifiers are ever used.

## Frontend

- **Settings → Alert notifications:** an explicit **Enable notifications on this device** button. Permission is never requested on page load. It shows the minimum severity, a test send, turning off, and the last 5 deliveries labelled honestly (accepted by push service / shown on this device / opened).
- **States:** unsupported browser; iOS/iPadOS not installed (Web Push there requires Add to Home Screen, iOS 16.4+); permission denied (with instructions); revoked since enabling (offers re-enable, removes the server subscription); server not configured. None of these block the app.
- **Alerts page:** a fallback notice when push is off, and `/#/alerts?alert=ID` highlights and scrolls to that alert.
- **Service worker:** handlers live in `public/push-sw.js`, loaded with `importScripts` into the **single** Workbox worker.

## What was tested

| Environment | Result |
| --- | --- |
| **Google Chrome 155.0.8059.40 (headless), macOS 26.5.2, Apple M2, real FCM** | Subscribed through the app's own button (endpoint on `fcm.googleapis.com`). **Foreground** (app open on the dashboard): FCM 201, service worker displayed the notification and reported it about 1 s later. **Background** (no app window open, browser running): FCM 201, displayed and receipt recorded. Notification text matched the minimal payload with the correct deep link. Click routing through the worker's real code moved an open window to `/#/alerts?alert=4`. |
| Same, clicking an OS notification | **Not automatable.** Chrome allows `focus()`/`openWindow()` only during a real notification click (user activation). Covered by unit tests with a simulated click. |
| Browser fully quit | **Not tested.** Desktop Chrome receives pushes only while the browser process runs (it can run in the background without windows). |
| Android Chrome, Edge, Firefox, iOS/iPadOS Safari (installed web app), macOS Safari | **Not tested**; no devices or browsers available here. |
| Backend against a local mock push service (SQLite + PostgreSQL 17) | 22 scenarios × 2 databases: decrypted payload contents, VAPID JWT signature/audience, TTL/Urgency/Topic headers, SSRF and key validation, ownership and token rotation, transactional enqueue (rollback leaves nothing), severity and enabled filters, deduplication including concurrent workers, 500/429 retries with `Retry-After`, network failures to max attempts, 410 cleanup, 413 no-retry, receipts with nonce verification, logs free of endpoints/keys/patient IDs, in-app alerts with push unconfigured, CORS |
| Frontend unit tests | 20: service-worker push/click handlers (safe text, malformed payloads, URL allowlist, receipts, focus vs open window), opt-in flows (unsupported, iOS needs install, no prompt when the server is unconfigured, denied, granted, reload, revoked, rotated endpoint, turn off), Settings states, alert deep-link highlighting and the fallback notice |

Before relying on push for a target platform, run the manual check on real hardware: enable in Settings → **Send test notification** → confirm the banner appears with the app foregrounded, backgrounded and closed → tap it → the Alerts view opens. The Settings delivery list should then show "opened on this device".
