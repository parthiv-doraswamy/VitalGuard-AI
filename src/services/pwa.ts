export async function registerPwa(): Promise<void> {
  if (!('serviceWorker' in navigator)) return;
  try {
    await navigator.serviceWorker.register('/service-worker.js', { scope: '/' });
  } catch (error) {
    console.error('VitalGuard service worker registration failed', error);
  }
}

export async function showSafetyNotification(title: string, body: string, tag: string): Promise<void> {
  if (!('Notification' in window) || Notification.permission !== 'granted') return;
  try {
    const registration = await navigator.serviceWorker.getRegistration('/');
    if (registration) {
      await registration.showNotification(title, {
        body,
        icon: '/icons/vitalguard-192.svg',
        badge: '/icons/vitalguard-192.svg',
        tag,
        data: { url: '/#/alerts' },
      });
    } else {
      new Notification(title, { body, tag });
    }
  } catch (error) {
    console.warn('Could not display VitalGuard notification', error);
  }
}
