/*
 * VitalGuard Web Push handlers, loaded with importScripts() into the app's single
 * Workbox service worker (vite.config.ts → workbox.importScripts). Not a second worker.
 *
 * - push: shows a lock-screen-safe notification (no patient data is ever sent), then
 *   reports "displayed" to the API. Receiving a push is not proof that the user saw it.
 * - notificationclick: focuses an open VitalGuard window and routes it in place, or
 *   opens a new one, then reports "clicked". Only this app's own hash routes are allowed.
 */
(function (sw) {
  var FALLBACK_URL = '/#/alerts';
  var ROUTE = /^\/#\/(alerts|settings|dashboard|live-demo)(\?[A-Za-z0-9=&_-]*)?$/;

  function safeUrl(url) {
    return typeof url === 'string' && ROUTE.test(url) ? url : FALLBACK_URL;
  }

  function parsePayload(text) {
    try {
      var payload = JSON.parse(text);
      if (!payload || payload.v !== 1 || (payload.type !== 'alert' && payload.type !== 'test')) return null;
      return payload;
    } catch (error) {
      return null;
    }
  }

  function notificationFor(payload) {
    if (!payload) {
      // Browsers require a visible notification for every push; never show raw data.
      return { title: 'VitalGuard', options: { body: 'Open VitalGuard to review new activity.', tag: 'vg-generic',
        icon: '/icons/icon-192.png', badge: '/icons/icon-192.png', data: { url: FALLBACK_URL } } };
    }
    return {
      title: String(payload.title || 'VitalGuard').slice(0, 80),
      options: {
        body: String(payload.body || '').slice(0, 160),
        tag: typeof payload.tag === 'string' ? payload.tag.slice(0, 40) : 'vg-alert',
        renotify: true,
        requireInteraction: payload.severity === 'critical',
        icon: '/icons/icon-192.png',
        badge: '/icons/icon-192.png',
        data: { url: safeUrl(payload.url), delivery_id: payload.delivery_id, receipt: payload.receipt || null },
      },
    };
  }

  function sendReceipt(data, eventName) {
    var receipt = data && data.receipt;
    if (!receipt || typeof receipt.url !== 'string' || !/^https?:\/\//.test(receipt.url) || !data.delivery_id) {
      return Promise.resolve();
    }
    return fetch(receipt.url, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ delivery_id: data.delivery_id, nonce: receipt.nonce, event: eventName }),
      keepalive: true,
    }).catch(function () { /* receipts are diagnostics only */ });
  }

  function openOrFocus(url) {
    var target = new URL(url, sw.location.origin).href;
    return sw.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(function (windows) {
      for (var i = 0; i < windows.length; i += 1) {
        var client = windows[i];
        if (new URL(client.url).origin === sw.location.origin) {
          // The page routes itself (HashRouter) without a reload; see src/services/pwa.ts.
          client.postMessage({ type: 'vg-navigate', url: url });
          // Browsers only allow focus() during a real notification click; routing still happens without it.
          return client.focus().catch(function () { return client; });
        }
      }
      return sw.clients.openWindow(target);
    });
  }

  sw.addEventListener('push', function (event) {
    var payload = event.data ? parsePayload(event.data.text()) : null;
    var notification = notificationFor(payload);
    event.waitUntil(sw.registration.showNotification(notification.title, notification.options).then(function () {
      return sendReceipt(notification.options.data, 'displayed');
    }));
  });

  sw.addEventListener('notificationclick', function (event) {
    event.notification.close();
    var data = event.notification.data || {};
    event.waitUntil(openOrFocus(safeUrl(data.url)).then(function () { return sendReceipt(data, 'clicked'); }));
  });

  // Exposed for unit tests.
  sw.vgPush = { safeUrl: safeUrl, parsePayload: parsePayload, notificationFor: notificationFor, openOrFocus: openOrFocus };
})(self);
