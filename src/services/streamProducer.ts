import { useCallback, useEffect, useRef, useState } from 'react';
import { ApiError, liveDemoApi } from './api.ts';
import type { ObservationEvent, StreamScenario, StreamSession } from './api.ts';

export type ProducerPhase = 'idle' | 'starting' | 'running' | 'paused' | 'stopped' | 'conflict' | 'error';

export interface ProducerState {
  phase: ProducerPhase;
  session: StreamSession | null;
  nextSequence: number;
  submitted: number;
  lastAck: { event: ObservationEvent; roundTripMs: number; duplicate: boolean } | null;
  consecutiveFailures: number;
  error: string | null;
  /** The other producer's session when a start was refused (409). */
  conflict: StreamSession | null;
}

export interface StartOptions { scenario: StreamScenario; intervalMs: number; producerKey?: string; takeover?: boolean }

const STORAGE_KEY = 'vg-live-producer';
const MAX_CONSECUTIVE_FAILURES = 3;

interface StoredProducer { sessionId: string; token: string }

function readStored(): StoredProducer | null {
  try {
    const value = JSON.parse(sessionStorage.getItem(STORAGE_KEY) || 'null') as StoredProducer | null;
    return value && typeof value.sessionId === 'string' && typeof value.token === 'string' ? value : null;
  } catch {
    return null;
  }
}
function writeStored(value: StoredProducer | null) {
  try {
    if (value) sessionStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    else sessionStorage.removeItem(STORAGE_KEY);
  } catch { /* storage unavailable: ownership lasts for this page only */ }
}

const INITIAL: ProducerState = {
  phase: 'idle', session: null, nextSequence: 0, submitted: 0, lastAck: null, consecutiveFailures: 0, error: null, conflict: null,
};

function sessionFromError(error: ApiError): StreamSession | null {
  const session = error.body.session ?? error.body.active_session;
  return session && typeof session === 'object' ? session as StreamSession : null;
}

/**
 * Drives one producer session from this browser tab (Laptop A).
 *
 * The backend owns sequencing, scoring and persistence; this loop only asks for
 * the next sequence each interval. A failed or timed-out request is retried with
 * the same sequence, which the backend answers idempotently, so retries never
 * create duplicate records. The producer token lives in sessionStorage, so only
 * this tab can control the session.
 */
export function useStreamProducer(onSubmit?: (sessionId: string, sequence: number, submittedAt: number) => void) {
  const [state, setState] = useState<ProducerState>(INITIAL);
  const owner = useRef<StoredProducer | null>(null);
  const nextSequence = useRef(0);
  const intervalMs = useRef(2000);
  const running = useRef(false);
  const inFlight = useRef(false);
  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const mounted = useRef(true);
  const onSubmitRef = useRef(onSubmit);
  onSubmitRef.current = onSubmit;

  const update = useCallback((patch: Partial<ProducerState>) => {
    if (mounted.current) setState((current) => ({ ...current, ...patch }));
  }, []);

  const halt = useCallback(() => {
    running.current = false;
    if (timer.current) clearTimeout(timer.current);
    timer.current = undefined;
  }, []);

  const releaseOwnership = useCallback(() => {
    owner.current = null;
    writeStored(null);
  }, []);

  const tick = useCallback(async () => {
    const current = owner.current;
    if (!running.current || inFlight.current || !current) return;
    inFlight.current = true;
    const sequence = nextSequence.current;
    const submittedAt = Date.now();
    onSubmitRef.current?.(current.sessionId, sequence, submittedAt);
    try {
      const result = await liveDemoApi.emit(current.sessionId, current.token, sequence);
      nextSequence.current = (result.event.sequence ?? sequence) + 1;
      if (mounted.current) {
        setState((previous) => ({
          ...previous, nextSequence: nextSequence.current, submitted: previous.submitted + (result.duplicate ? 0 : 1),
          lastAck: { event: result.event, roundTripMs: Date.now() - submittedAt, duplicate: result.duplicate },
          consecutiveFailures: 0, error: null,
          session: previous.session ? { ...previous.session, next_sequence: nextSequence.current, events_emitted: nextSequence.current } : previous.session,
        }));
      }
    } catch (error) {
      const apiError = error instanceof ApiError ? error : new ApiError(0, {}, 'Unexpected producer error');
      const session = sessionFromError(apiError);
      if (apiError.code === 'sequence_out_of_order' && typeof apiError.body.expected_sequence === 'number') {
        nextSequence.current = apiError.body.expected_sequence;
        update({ nextSequence: nextSequence.current });
      } else if (apiError.code === 'session_paused') {
        halt();
        if (mounted.current) setState((previous) => ({ ...previous, phase: 'paused', session: session ?? previous.session, error: null }));
      } else if (apiError.code && ['session_stopped', 'session_complete', 'session_changed'].includes(apiError.code)) {
        halt();
        releaseOwnership();
        update({ phase: 'stopped', session, error: apiError.message });
      } else if (apiError.status === 403 || apiError.status === 404) {
        halt();
        releaseOwnership();
        update({ phase: 'error', error: 'This browser no longer controls the stream session.' });
      } else if (apiError.status !== 429) {
        // Network/5xx: keep the same sequence so the retry is idempotent.
        if (mounted.current) {
          setState((previous) => {
            const failures = previous.consecutiveFailures + 1;
            if (failures >= MAX_CONSECUTIVE_FAILURES) halt();
            return { ...previous, consecutiveFailures: failures, error: apiError.message,
              phase: failures >= MAX_CONSECUTIVE_FAILURES ? 'error' : previous.phase };
          });
        }
      }
    } finally {
      inFlight.current = false;
      if (running.current) timer.current = setTimeout(() => { void tick(); }, intervalMs.current);
    }
  }, [halt, releaseOwnership, update]);

  const run = useCallback(() => {
    running.current = true;
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => { void tick(); }, 0);
  }, [tick]);

  const start = useCallback(async (options: StartOptions) => {
    halt();
    update({ ...INITIAL, phase: 'starting' });
    try {
      const result = await liveDemoApi.start({ scenario: options.scenario, interval_ms: options.intervalMs, takeover: options.takeover },
        options.producerKey);
      owner.current = { sessionId: result.session.session_id, token: result.producer_token };
      writeStored(owner.current);
      nextSequence.current = 0;
      intervalMs.current = result.session.interval_ms;
      update({ phase: 'running', session: result.session, nextSequence: 0 });
      run();
    } catch (error) {
      const apiError = error instanceof ApiError ? error : new ApiError(0, {}, 'Could not start the stream');
      if (apiError.code === 'producer_active') update({ phase: 'conflict', conflict: sessionFromError(apiError), error: apiError.message });
      else update({ phase: 'error', error: apiError.message });
    }
  }, [halt, run, update]);

  const control = useCallback(async (action: 'pause' | 'resume' | 'stop') => {
    const current = owner.current;
    if (!current) return;
    if (action !== 'resume') halt();
    try {
      const { session } = await liveDemoApi.control(current.sessionId, current.token, action);
      if (action === 'stop') {
        releaseOwnership();
        update({ phase: 'stopped', session, error: null });
      } else if (action === 'pause') {
        update({ phase: 'paused', session, error: null });
      } else {
        nextSequence.current = session.next_sequence;
        update({ phase: 'running', session, error: null, consecutiveFailures: 0, nextSequence: session.next_sequence });
        run();
      }
    } catch (error) {
      const apiError = error instanceof ApiError ? error : new ApiError(0, {}, 'Stream control failed');
      if (apiError.code === 'session_stopped') {
        releaseOwnership();
        update({ phase: 'stopped', session: sessionFromError(apiError), error: apiError.message });
      } else {
        update({ phase: 'error', error: `${action} failed: ${apiError.message}` });
      }
    }
  }, [halt, releaseOwnership, run, update]);

  /** Re-sync with the backend after an error, continuing from the server's next sequence. */
  const retry = useCallback(async () => {
    const current = owner.current;
    if (!current) { update({ ...INITIAL }); return; }
    try {
      const { session } = await liveDemoApi.getSession(current.sessionId);
      nextSequence.current = session.next_sequence;
      intervalMs.current = session.interval_ms;
      if (session.status === 'running') { update({ phase: 'running', session, error: null, consecutiveFailures: 0 }); run(); }
      else if (session.status === 'paused') update({ phase: 'paused', session, error: null, consecutiveFailures: 0 });
      else { releaseOwnership(); update({ phase: 'stopped', session, error: null }); }
    } catch (error) {
      update({ error: error instanceof Error ? error.message : 'Backend unavailable' });
    }
  }, [releaseOwnership, run, update]);

  const reset = useCallback(() => { halt(); update({ ...INITIAL }); }, [halt, update]);

  // Restore ownership after a reload of this tab (sessionStorage is per tab).
  useEffect(() => {
    mounted.current = true;
    const stored = readStored();
    if (stored) {
      owner.current = stored;
      void retry();
    }
    return () => { mounted.current = false; halt(); };
  }, []); // Restore runs once per mount.

  return {
    state,
    start,
    pause: () => control('pause'),
    resume: () => control('resume'),
    stop: () => control('stop'),
    retry,
    reset,
    ownsSession: (sessionId: string | null | undefined) => !!sessionId && owner.current?.sessionId === sessionId,
  };
}

export type StreamProducer = ReturnType<typeof useStreamProducer>;
