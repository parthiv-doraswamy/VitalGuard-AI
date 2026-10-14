# Progressive Web App

> VitalGuard AI remains a synthetic-data prototype. Installing it does not make it a
> clinical tool, and offline mode never serves patient or prediction data from cache.

## What is configured

| Piece | Where | Notes |
| --- | --- | --- |
| Manifest | `public/manifest.webmanifest` (the only manifest; the plugin's generator is off) | `display: standalone`, `start_url: /?source=pwa`, scope `/`, theme `#0d9488`, background `#f5f8fb`, shortcuts to Dashboard/Alerts/Live demo |
| Icons | `public/icons/` | 192 and 512 px (`any`), 512 px `maskable` with the artwork inside the 80% safe zone, 180 px Apple touch icon, 32 px favicon, SVG master. Regenerate with `node scripts/generate-icons.mjs`. |
| Service worker | `vite-plugin-pwa` **1.3.0** (pinned; Workbox 7.4.1) generates `dist/sw.js` | Exactly one worker, registered only in `src/services/pwa.ts`, and only in production builds |
| HTML | `index.html` | Manifest link, light/dark `theme-color`, icons, `viewport-fit=cover`, iOS standalone meta tags |
| Build check | `npm run verify:pwa` (in CI after `npm run build`) | Fails on invalid manifest fields, wrong icon pixel sizes, a missing or second worker, duplicate precache entries, non-font runtime routes, or API-like precached URLs |

## Caching policy

| Content | Strategy |
| --- | --- |
| `index.html`, built JS/CSS, icons, manifest (11 files, about 1.1 MB) | Precached, revisioned per build; outdated caches are cleaned up |
| Navigation requests | Served `index.html` from the precache (HashRouter), except `/api/*` |
| Google Fonts stylesheet / font files | Stale-while-revalidate / cache-first (public, non-sensitive) |
| **Everything else, including all API calls** (observations, history, timelines, alerts, predictions, model info, live-demo, `/health`) and the WebSocket | **Not cached.** The worker has no route for them, so they always go to the network |
| Login and demo-session data | `sessionStorage`, never in Cache Storage |

Verified (2026-10-14, Chromium): after a session with 14 successful API responses (prediction, alerts, history, live stream), Cache Storage held 14 entries (precache plus two font caches) and **0** API responses.

## Offline and stale-data behaviour

| Area | Offline | Backend unreachable or reconnecting |
| --- | --- | --- |
| App shell, navigation, login, protected routes | Work from precache | Work |
| Local synthetic simulation (dashboard cohort, charts) | Works; labelled "runs in this browser only" | Works |
| Backend panels (history, timeline, trends, alert inbox, model info) | Show their "unavailable" error states; nothing from cache | Same |
| Live stream panel / event log | Keeps the last received events, labelled `offline`; red banner dates them ("from HH:MM:SS or earlier and may be out of date") | Amber banner: "Reconnecting… live values may be stale (last live event HH:MM:SS)"; missed events are recovered after reconnecting |
| Predictions (Settings) | Buttons disabled with "unavailable offline"; nothing is computed or reused | Request fails with the existing error message |
| Alert acknowledge/resolve, start live stream | Disabled | Request fails visibly |

Connection honesty:
- The live socket now sends a heartbeat and closes the connection if no pong arrives within 10 s. A dropped network can no longer show "connected".
- It switches to `offline` immediately on the browser's `offline` event and reconnects as soon as `online` fires, without waiting for the retry backoff.

## Updates

`registerType: 'prompt'`. A new deployment's worker installs in the background and **waits**:

1. The page shows "A new version is available" with **Update now** / **Later**. Nothing reloads by itself.
2. **Update now** activates the new worker and reloads once. The demo session (`sessionStorage`) and any running live-demo producer survive the reload.
3. **Later** keeps the current version, including across ordinary reloads, until the user accepts or every tab is closed.

Update checks run on load, hourly, and when the tab becomes visible again. Render serves files with `cache-control: public, max-age=0, s-maxage=300`, so the CDN may serve the previous `sw.js` for up to 5 minutes after a deploy.

Verified locally with two real builds: A ran; deploying B showed the prompt with B waiting while A kept running; **Later** plus a reload still ran A; **Update now** switched to B in one reload, still signed in.

## Mobile

- 44 × 44 px minimum touch targets on coarse pointers; no 300 ms tap delay.
- Safe-area padding for notched phones in standalone mode; pull-to-refresh disabled in standalone mode.
- The navigation drawer sits above the update/offline toasts.
- Audited in Chromium with Pixel 7 emulation (412 px): every visible control is at least 44 px tall apart from the visually hidden skip link.

## HTTPS

Checked against the live site on 2026-10-14: `http://vitalguard-ai-g215.onrender.com/` → `301` to HTTPS; HTTPS responses carry `strict-transport-security: max-age=315360000; includeSubdomains; preload`. The API (`vitalguard-risk-api.onrender.com`) is HTTPS. Real files, such as `/sw.js` and `/manifest.webmanifest`, are served ahead of the SPA rewrite, as existing `/assets/*.js` are today.

## Verified vs not verified

**Verified (headless Chromium, local production build):**
- Chromium's installability check (DevTools `Page.getInstallabilityErrors`) returns no errors, and the manifest parses without errors.
- Exactly one worker, which controls the page.
- With the network cut, the app shell, login and protected routes load and backend actions are disabled.
- Caches contain no API data.
- The update flow above.

**Not verified here (needs real devices or a deployment):**
- Actual installation and standalone launch on desktop Chrome/Edge and Android Chrome.
- iOS/iPadOS Safari "Add to Home Screen". Safari ignores parts of the manifest and handles storage, background and service-worker lifetimes differently.
- Firefox desktop, which does not offer installation.
- The update flow on the deployed Render site.

Offline support covers the app shell only. It is not offline clinical functionality, and behaviour differs across browsers and operating systems.

### After deploying (manual checklist)
1. Chrome DevTools → Application → Manifest: no errors; the install icon appears in the address bar. Install, then launch: it opens in its own window (standalone).
2. Application → Service workers: one `sw.js`, activated. Cache Storage: only `workbox-precache-*`, `vg-google-fonts-*`.
3. DevTools Network → Offline, then reload: the shell loads, the red offline banner shows, and backend actions are disabled.
4. Android Chrome: menu → Install app; launch from the home screen.
5. Deploy any change, wait 5 minutes or more, reopen the installed app: the update prompt appears and **Update now** loads the new version.
