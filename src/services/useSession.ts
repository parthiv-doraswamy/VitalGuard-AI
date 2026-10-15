import { useSyncExternalStore } from 'react';
import { can, getSession, onSessionChange, type Permission, type Session } from './auth.ts';

/** The signed-in demo user, re-rendering on sign-in and sign-out. */
export function useSession(): Session | null {
  return useSyncExternalStore(onSessionChange, getSession, getSession);
}

export function useCan(permission: Permission): boolean {
  return can(useSession(), permission);
}
