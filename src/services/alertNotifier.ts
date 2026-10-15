import type { AlertItem, Patient } from '../types/index.ts';
import { parseBackendAlertId } from '../store/liveIngest.ts';

/**
 * System notification for an alert received over the live channel while the app is open.
 *
 * Uses the same tag as the Web Push payload (vg-alert-<id>), so when push is also enabled
 * the operating system replaces rather than duplicates the notification. Like the push
 * payload, the text carries only the ward and bed, never the patient's name or vitals,
 * because it can appear on a lock screen.
 */
export async function showAlertNotification(alert: AlertItem, patient: Patient | undefined): Promise<boolean> {
  if (typeof window === 'undefined' || !('Notification' in window) || Notification.permission !== 'granted') return false;
  const backendId = parseBackendAlertId(alert.id);
  const where = patient ? ` (${patient.ward} · bed ${patient.bed})` : '';
  const title = `VitalGuard: ${alert.severity} alert${where}`;
  const options: NotificationOptions & { renotify?: boolean } = {
    body: 'One of your assigned demo patients needs review. Open VitalGuard to see it.',
    tag: backendId ? `vg-alert-${backendId}` : `vg-local-${alert.id}`,
    renotify: true,
    requireInteraction: alert.severity === 'critical',
    icon: '/icons/icon-192.png',
    badge: '/icons/icon-192.png',
    data: { url: backendId ? `/#/alerts?alert=${backendId}` : '/#/alerts' },
  };
  try {
    const registration = await navigator.serviceWorker?.getRegistration();
    if (registration) {
      await registration.showNotification(title, options);
    } else {
      new Notification(title, options);
    }
    return true;
  } catch {
    return false;
  }
}

/** Ask for notification permission (must run from a click). Returns the resulting permission. */
export async function requestAlertPermission(): Promise<NotificationPermission | 'unsupported'> {
  if (typeof window === 'undefined' || !('Notification' in window)) return 'unsupported';
  if (Notification.permission !== 'default') return Notification.permission;
  return Notification.requestPermission();
}
