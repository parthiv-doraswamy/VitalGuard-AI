import { createContext, useContext } from 'react';
import type { StreamSession } from './api.ts';
import type { ClockSample, LiveStatus, LoggedEvent } from './liveEvents.ts';
import type { StreamProducer } from './streamProducer.ts';

export interface LiveEventsState {
  status: LiveStatus;
  /** Newest first, unique by event_id. */
  log: LoggedEvent[];
  latest: LoggedEvent | null;
  /** Unique committed observation events seen in this tab (live + recovered). */
  eventCount: number;
  recoveredCount: number;
  alertsReceived: number;
  session: StreamSession | null;
  clock: ClockSample | null;
  latency: { lastMs: number | null; averageMs: number | null; samples: number };
  errors: { count: number; last: string | null };
  lastCatchUpAt: string | null;
  /** Null outside a LiveEventsProvider (for example in isolated component tests). */
  producer: StreamProducer | null;
}

export const DEFAULT_LIVE_STATE: LiveEventsState = {
  status: 'connecting', log: [], latest: null, eventCount: 0, recoveredCount: 0, alertsReceived: 0, session: null,
  clock: null, latency: { lastMs: null, averageMs: null, samples: 0 }, errors: { count: 0, last: null },
  lastCatchUpAt: null, producer: null,
};

export const LiveEventsContext = createContext<LiveEventsState>(DEFAULT_LIVE_STATE);

/** Shared backend live channel for this tab: one WebSocket, one event log, one producer. */
export function useLiveEvents() {
  return useContext(LiveEventsContext);
}
