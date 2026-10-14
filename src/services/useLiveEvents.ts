import { useEffect, useState } from 'react';
import { createLiveSocket, type LiveEvent } from './liveEvents.ts';

export function useLiveEvents() {
  const [status, setStatus] = useState<'connecting' | 'connected' | 'reconnecting' | 'offline'>('connecting');
  const [lastEvent, setLastEvent] = useState<LiveEvent | null>(null);
  const [eventCount, setEventCount] = useState(0);

  useEffect(() => createLiveSocket((event) => {
    if (event.type === 'observation.created' || event.type === 'alert.created') {
      setLastEvent(event);
      setEventCount((count) => count + 1);
    }
  }, setStatus), []);

  return { status, lastEvent, eventCount };
}
