import { useEffect, useState } from 'react';
import { BellRing, Download, Smartphone, ShieldCheck } from 'lucide-react';

type InstallPromptEvent = Event & { prompt: () => Promise<void>; userChoice: Promise<{ outcome: 'accepted' | 'dismissed' }> };

export function PwaNotificationSettings() {
  const [permission, setPermission] = useState<NotificationPermission>(() =>
    'Notification' in window ? Notification.permission : 'unsupported'
  );
  const [installed, setInstalled] = useState(false);
  const [installPrompt, setInstallPrompt] = useState<InstallPromptEvent | null>(null);
  const [message, setMessage] = useState('');

  useEffect(() => {
    setInstalled(window.matchMedia('(display-mode: standalone)').matches || Boolean((navigator as Navigator & { standalone?: boolean }).standalone));
    const onPrompt = (event: Event) => { event.preventDefault(); setInstallPrompt(event as InstallPromptEvent); };
    const onInstalled = () => { setInstalled(true); setInstallPrompt(null); setMessage('VitalGuard AI is installed on this device.'); };
    window.addEventListener('beforeinstallprompt', onPrompt);
    window.addEventListener('appinstalled', onInstalled);
    return () => {
      window.removeEventListener('beforeinstallprompt', onPrompt);
      window.removeEventListener('appinstalled', onInstalled);
    };
  }, []);

  async function enableNotifications() {
    if (!('Notification' in window)) {
      setMessage('This browser does not support web notifications. Try an up-to-date mobile browser.');
      return;
    }
    try {
      const result = await Notification.requestPermission();
      setPermission(result);
      setMessage(result === 'granted' ? 'Notifications enabled on this device.' : result === 'denied' ? 'Notifications are blocked in browser settings.' : 'Notification permission was not granted.');
    } catch {
      setMessage('Could not request notification permission in this browser.');
    }
  }

  async function sendTest() {
    if (!('Notification' in window) || Notification.permission !== 'granted') {
      setMessage('Enable notifications first, then send a test alert.');
      return;
    }
    try {
      const registration = await navigator.serviceWorker.getRegistration('/');
      if (registration) await registration.showNotification('VitalGuard AI test alert', {
        body: 'Mobile notifications are working on this device. Demo alert only; not a clinical alarm.',
        icon: '/icons/vitalguard-192.svg',
        badge: '/icons/vitalguard-192.svg',
        tag: 'vitalguard-test',
        data: { url: '/#/alerts' },
      });
      else new Notification('VitalGuard AI test alert', { body: 'Notifications are working. Demo alert only.' });
      setMessage('Test notification sent. Check your device notification tray.');
    } catch {
      setMessage('The browser could not display the test notification.');
    }
  }

  async function installApp() {
    if (!installPrompt) {
      setMessage('On your phone, open the browser menu and choose “Add to Home Screen” or “Install app”.');
      return;
    }
    await installPrompt.prompt();
    const choice = await installPrompt.userChoice;
    if (choice.outcome === 'accepted') setMessage('Installation started.');
    setInstallPrompt(null);
  }

  return (
    <section className="card p-5 sm:p-6 min-w-0" aria-label="PWA and mobile notifications">
      <div className="flex items-start gap-3">
        <span className="h-10 w-10 rounded-2xl bg-teal-50 text-teal-700 dark:bg-teal-950/60 dark:text-teal-300 grid place-items-center"><Smartphone size={19} aria-hidden /></span>
        <div className="min-w-0">
          <p className="eyebrow">Mobile experience</p>
          <h3 className="font-display font-bold text-[16px] tracking-tight mt-1">Install app & notifications</h3>
          <p className="text-xs text-slate-500 mt-1">Install VitalGuard on your home screen and allow device notifications for demo safety signals.</p>
        </div>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn-primary inline-flex items-center gap-2" onClick={installApp}><Download size={15} aria-hidden />{installed ? 'App installed' : 'Install app'}</button>
        <button className="btn-ghost inline-flex items-center gap-2" onClick={enableNotifications} disabled={permission === 'granted'}><BellRing size={15} aria-hidden />{permission === 'granted' ? 'Notifications enabled' : 'Enable notifications'}</button>
        <button className="btn-ghost inline-flex items-center gap-2" onClick={sendTest} disabled={permission !== 'granted'}><ShieldCheck size={15} aria-hidden />Send test alert</button>
      </div>
      <p className="text-xs text-slate-500 mt-3" role="status">{message || (permission === 'granted' ? 'Permission granted on this browser.' : permission === 'denied' ? 'Permission blocked; enable it in browser site settings.' : 'Permission: not enabled.')}</p>
      <p className="text-[11px] leading-relaxed text-slate-400 mt-2">Important: test and simulated alerts are demo-only. Notifications while the app is closed require a configured push service and server-side event sender; browser permission alone does not provide background push.</p>
    </section>
  );
}
