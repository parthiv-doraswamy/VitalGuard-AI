import { useCallback } from 'react';
import { useSimulation } from './useSimulation.ts';
import { useLiveEvents } from '../services/useLiveEvents.ts';
import { useSession } from '../services/useSession.ts';
import { can } from '../services/auth.ts';

export type MonitoringSource = 'backend' | 'remote' | 'local' | 'idle';

/**
 * One control for "live monitoring", whichever engine drives it:
 * - backend: this tab produces a cohort stream; the backend scores every patient and every
 *   signed-in device (including the assigned doctors) receives the same vitals and alerts.
 * - remote:  another device is producing the stream; this one only watches.
 * - local:   offline fallback (no backend session): the in-browser simulation, not shared.
 */
export function useMonitoring() {
  const sim = useSimulation();
  const { producer, session: stream, status } = useLiveEvents();
  const session = useSession();
  const canControl = can(session, 'controlStream');
  const backendReady = !!session?.token && status === 'connected' && !!producer;
  const streamRunning = stream?.status === 'running' && stream.mode === 'cohort';
  const ownsStream = !!producer && producer.ownsSession(stream?.session_id);

  const source: MonitoringSource = streamRunning ? (ownsStream ? 'backend' : 'remote') : sim.running ? 'local' : 'idle';
  const running = source !== 'idle';
  const phase = producer?.state.phase;

  const start = useCallback(() => {
    if (!canControl) return;
    if (backendReady && producer) {
      if (sim.running) sim.pause();
      const intervalMs = sim.speed === 'slow' ? 4000 : sim.speed === 'fast' ? 1000 : 2000;
      void producer.start({ mode: 'cohort', scenario: 'worsening', intervalMs: Math.max(500, intervalMs / sim.multiplier), takeover: true });
    } else {
      sim.start();
    }
  }, [backendReady, canControl, producer, sim]);

  const pause = useCallback(() => {
    if (source === 'backend' && producer) void producer.pause();
    else if (source === 'local') sim.pause();
  }, [producer, sim, source]);

  const resume = useCallback(() => { if (producer && phase === 'paused') void producer.resume(); }, [phase, producer]);
  const stop = useCallback(() => {
    if (source === 'backend' && producer) void producer.stop();
    else sim.pause();
  }, [producer, sim, source]);

  const sourceLabel = source === 'backend' ? 'Backend stream from this device · shared with every signed-in device'
    : source === 'remote' ? 'Backend stream from another device'
      : source === 'local' ? 'Local in-browser simulation (offline fallback, not shared)'
        : 'Not running';

  return {
    running, source, sourceLabel, canControl, backendReady,
    /** Pausing a stream another device produces is not possible from here. */
    canPause: source === 'backend' || source === 'local',
    pausedHere: phase === 'paused',
    busy: phase === 'starting',
    error: producer?.state.error ?? null,
    tick: source === 'local' ? sim.tick : sim.streamTick ?? stream?.next_sequence ?? 0,
    start, pause, resume, stop,
  };
}
