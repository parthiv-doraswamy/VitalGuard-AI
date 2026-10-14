import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { act, render, renderHook, screen, waitFor } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import type { ObservationEvent, StreamSession } from '../services/api.ts';
import { clockSampleFromPong, deliveryLatencyMs, mergeEvents, type LoggedEvent } from '../services/liveEvents.ts';
import { useStreamProducer } from '../services/streamProducer.ts';
import { LiveEventsProvider } from '../services/LiveEventsProvider.tsx';
import { DEFAULT_LIVE_STATE, LiveEventsContext } from '../services/useLiveEvents.ts';
import { LiveStatusPanel } from '../components/live/LiveStatusPanel.tsx';
import { LiveEventLog } from '../components/live/LiveEventLog.tsx';

const SESSION: StreamSession = {
  session_id: 'aaaaaaaa-1111-2222-3333-444444444444', patient_id: 'DEMO-STREAM-AAAAAA', scenario: 'worsening',
  status: 'running', interval_ms: 10, next_sequence: 0, events_emitted: 0, last_observation_id: null,
  created_at: '2026-10-14T10:00:00+00:00', updated_at: null, last_emit_at: null, stopped_at: null, stop_reason: null,
  max_sequence: 1000, demo_only: true,
};

function makeEvent(id: number, sequence: number, extra: Partial<ObservationEvent> = {}): ObservationEvent {
  return {
    type: 'observation.created', event_id: id, observation_id: id, session_id: SESSION.session_id, sequence,
    patient_id: SESSION.patient_id, created_at: '2026-10-14T10:00:01+00:00', timestamp: '2026-10-14T10:00:01+00:00',
    observation: { heart_rate: 96, spo2: 93, systolic_bp: 109, diastolic_bp: 72, respiratory_rate: 23, temperature: 37.7 },
    model_version: 'synthetic-logreg-0.1.0', prediction: { risk_score: 71, risk_level: 'high' },
    alert: null, server_received_at: '2026-10-14T10:00:01.000+00:00', published_at: '2026-10-14T10:00:01.050+00:00',
    demo_only: true, data_origin: 'synthetic', ...extra,
  };
}
const logged = (event: ObservationEvent, origin: 'live' | 'recovered' = 'live'): LoggedEvent =>
  ({ event, receivedAt: 0, origin, latencyMs: null, localLatencyMs: null });

function jsonResponse(body: unknown, status = 200) {
  return { ok: status < 400, status, json: async () => body } as Response;
}

afterEach(() => {
  vi.unstubAllGlobals();
  vi.restoreAllMocks();
  sessionStorage.clear();
});

describe('event merging and timing', () => {
  it('keeps one copy per event_id, newest first, when live and recovered events overlap', () => {
    const first = mergeEvents([], [logged(makeEvent(5, 0)), logged(makeEvent(6, 1))]);
    const second = mergeEvents(first.log, [logged(makeEvent(6, 1), 'recovered'), logged(makeEvent(7, 2), 'recovered')]);
    expect(second.log.map((item) => item.event.event_id)).toEqual([7, 6, 5]);
    expect(second.added.map((item) => item.event.event_id)).toEqual([7]);
    expect(second.log.find((item) => item.event.event_id === 6)?.origin).toBe('live');
  });

  it('estimates clock offset from a timed pong and corrects delivery latency', () => {
    // Local clock is 1000 ms behind the server; the ping round trip took 40 ms.
    const sample = clockSampleFromPong({ type: 'pong', client_time: 10_000, server_time: new Date(11_020).toISOString() }, 10_040);
    expect(sample).toEqual({ offsetMs: 1000, rttMs: 40 });
    const event = makeEvent(1, 0, { server_received_at: new Date(20_000).toISOString() });
    // Received locally at 19_100 ⇒ 20_100 on the server clock ⇒ 100 ms after server receipt.
    expect(deliveryLatencyMs(event, 19_100, sample)).toBe(100);
    expect(deliveryLatencyMs({ ...event, server_received_at: null }, 19_100, sample)).toBeNull();
    expect(clockSampleFromPong({ type: 'pong' }, 1)).toBeNull();
  });
});

describe('receiver panel', () => {
  it('shows the backend event values without computing anything locally', () => {
    const event = makeEvent(42, 3, { alert: { id: 9, patient_id: SESSION.patient_id, severity: 'high', status: 'open', title: 'High demo risk score', created_at: null } });
    render(
      <MemoryRouter>
        <LiveEventsContext.Provider value={{ ...DEFAULT_LIVE_STATE, status: 'connected', session: SESSION, latest: logged(event), log: [logged(event)], eventCount: 1 }}>
          <LiveStatusPanel />
          <LiveEventLog />
        </LiveEventsContext.Provider>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('live-latest-event-id')).toHaveTextContent('#42');
    expect(screen.getByTestId('live-latest-score')).toHaveTextContent('71');
    expect(screen.getByTestId('live-latest-model')).toHaveTextContent('synthetic-logreg-0.1.0');
    expect(screen.getByTestId('live-latest-alert')).toHaveTextContent('Alert #9');
    expect(screen.getByTestId('live-session-status')).toHaveTextContent('Streaming');
    expect(screen.getByText(/Receiver mode/)).toBeInTheDocument();
    expect(screen.getAllByTestId('live-log-row')).toHaveLength(1);
  });

  it('stays in receiver mode and explains a stopped stream', () => {
    render(
      <MemoryRouter>
        <LiveEventsContext.Provider value={{ ...DEFAULT_LIVE_STATE, status: 'connected', session: { ...SESSION, status: 'stopped', stop_reason: 'producer_stopped' } }}>
          <LiveStatusPanel />
        </LiveEventsContext.Provider>
      </MemoryRouter>,
    );
    expect(screen.getByTestId('live-session-status')).toHaveTextContent('Stopped (producer stopped)');
    expect(screen.getByText(/Receiver mode/)).toBeInTheDocument();
  });
});

describe('stream producer', () => {
  it('retries a failed submission with the same sequence and then advances', async () => {
    const sequences: number[] = [];
    let emitCalls = 0;
    vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
      if (url.endsWith('/sessions')) return jsonResponse({ session: SESSION, producer_token: 'tok', replaced_session: null }, 201);
      const { sequence } = JSON.parse(String(init?.body));
      sequences.push(sequence);
      emitCalls += 1;
      if (emitCalls === 2) throw new TypeError('network down');
      return jsonResponse({ event: makeEvent(100 + sequence, sequence), duplicate: false });
    }));
    const { result, unmount } = renderHook(() => useStreamProducer());
    await act(async () => { await result.current.start({ scenario: 'worsening', intervalMs: 10 }); });
    await waitFor(() => expect(sequences.length).toBeGreaterThanOrEqual(4));
    unmount();
    // Sequence 1 failed once and was retried as 1, never skipped or duplicated as 2.
    expect(sequences.slice(0, 4)).toEqual([0, 1, 1, 2]);
    expect(JSON.parse(sessionStorage.getItem('vg-live-producer') || '{}').token).toBe('tok');
  });

  it('adopts a pause made on the server and reports another active producer as a conflict', async () => {
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.endsWith('/sessions')) return jsonResponse({ session: SESSION, producer_token: 'tok', replaced_session: null }, 201);
      return jsonResponse({ detail: 'The stream session is paused.', error: 'session_paused', session: { ...SESSION, status: 'paused' } }, 409);
    }));
    const { result } = renderHook(() => useStreamProducer());
    await act(async () => { await result.current.start({ scenario: 'stable', intervalMs: 10 }); });
    await waitFor(() => expect(result.current.state.phase).toBe('paused'));

    vi.stubGlobal('fetch', vi.fn(async () => jsonResponse({ detail: 'Another producer is already streaming.', error: 'producer_active', active_session: SESSION }, 409)));
    await act(async () => { await result.current.start({ scenario: 'stable', intervalMs: 10 }); });
    expect(result.current.state.phase).toBe('conflict');
    expect(result.current.state.conflict?.session_id).toBe(SESSION.session_id);
  });
});

class FakeSocket {
  static instances: FakeSocket[] = [];
  static OPEN = 1;
  readyState = 0;
  sent: string[] = [];
  onopen: (() => void) | null = null;
  onmessage: ((message: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) { FakeSocket.instances.push(this); }
  send(data: string) { this.sent.push(data); }
  close() { this.readyState = 3; this.onclose?.(); }
  open() { this.readyState = 1; this.onopen?.(); }
  emit(data: unknown) { this.onmessage?.({ data: JSON.stringify(data) }); }
}

describe('live events provider', () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
  });

  it('recovers events missed while disconnected without double counting', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    const catchUpCalls: string[] = [];
    vi.stubGlobal('fetch', vi.fn(async (url: string) => {
      if (url.includes('/api/v1/observations?limit=1')) return jsonResponse({ items: [{ id: 10 }], count: 1, limit: 1, next_before_id: null });
      if (url.includes('/sessions/current')) return jsonResponse({ session: SESSION });
      if (url.includes('/live-demo/events')) {
        catchUpCalls.push(url);
        return jsonResponse({ items: [makeEvent(11, 0), makeEvent(12, 1), makeEvent(13, 2)], count: 3, next_after_id: null });
      }
      return jsonResponse({});
    }));
    render(<MemoryRouter><LiveEventsProvider><LiveStatusPanel /></LiveEventsProvider></MemoryRouter>);

    await act(async () => { FakeSocket.instances[0].open(); });
    await waitFor(() => expect(screen.getByTestId('live-session-status')).toHaveTextContent('Streaming'));
    await act(async () => { FakeSocket.instances[0].emit(makeEvent(11, 0)); });
    expect(screen.getByTestId('live-latest-event-id')).toHaveTextContent('#11');

    // Drop the connection; the client reconnects after its backoff and catches up.
    await act(async () => { FakeSocket.instances[0].close(); });
    expect(screen.getByTestId('live-connection-status')).toHaveTextContent('reconnecting');
    await act(async () => { await vi.advanceTimersByTimeAsync(1100); });
    await act(async () => { FakeSocket.instances[1].open(); });
    await waitFor(() => expect(screen.getByTestId('live-latest-event-id')).toHaveTextContent('#13'));

    expect(catchUpCalls[0]).toContain('after_id=11');
    expect(screen.getByTestId('live-events-received')).toHaveTextContent('3');
    expect(screen.getByTestId('live-events-recovered')).toHaveTextContent('2');
    // A late live copy of a recovered event is ignored.
    await act(async () => { FakeSocket.instances[1].emit(makeEvent(12, 1)); });
    expect(screen.getByTestId('live-events-received')).toHaveTextContent('3');
    vi.useRealTimers();
  });
});

describe('connection honesty', () => {
  beforeEach(() => {
    FakeSocket.instances = [];
    vi.stubGlobal('WebSocket', FakeSocket);
  });

  it('drops a socket that stops answering pings instead of claiming to be connected', async () => {
    vi.useFakeTimers();
    const statuses: string[] = [];
    const { createLiveSocket } = await import('../services/liveEvents.ts');
    const stop = createLiveSocket(() => undefined, (status) => statuses.push(status), { heartbeatMs: 1000, pongTimeoutMs: 3000 });
    FakeSocket.instances[0].open();
    expect(statuses[statuses.length - 1]).toBe('connected');
    vi.advanceTimersByTime(3100);  // ping sent on open, no pong
    expect(statuses[statuses.length - 1]).toBe('reconnecting');
    stop();
    vi.useRealTimers();
  });

  it('reports offline immediately and reconnects as soon as the browser is back online', async () => {
    vi.useFakeTimers();
    const statuses: string[] = [];
    const { createLiveSocket } = await import('../services/liveEvents.ts');
    const stop = createLiveSocket(() => undefined, (status) => statuses.push(status));
    FakeSocket.instances[0].open();
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, get: () => false });
    window.dispatchEvent(new Event('offline'));
    expect(statuses[statuses.length - 1]).toBe('offline');
    vi.advanceTimersByTime(60000);
    expect(FakeSocket.instances).toHaveLength(1);  // no futile retries while offline
    Object.defineProperty(window.navigator, 'onLine', { configurable: true, get: () => true });
    window.dispatchEvent(new Event('online'));
    expect(FakeSocket.instances).toHaveLength(2);
    FakeSocket.instances[1].open();
    expect(statuses[statuses.length - 1]).toBe('connected');
    stop();
    vi.useRealTimers();
  });
});
