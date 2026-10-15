import '@testing-library/jest-dom';
import { cleanup } from '@testing-library/react';
import { afterEach } from 'vitest';
import { clearSession } from '../services/auth.ts';
afterEach(() => {
  cleanup();
  document.documentElement.classList.remove('dark');
  try { localStorage.clear(); } catch { /* ignore */ }
  clearSession();
});
class RO {
  observe() {}
  unobserve() {}
  disconnect() {}
}
(globalThis as Record<string, unknown>).ResizeObserver = RO;

