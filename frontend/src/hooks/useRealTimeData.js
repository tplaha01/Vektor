import { useEffect, useRef, useState, useCallback } from 'react';

const API_CACHE = {};
const IN_FLIGHT = {};
const CACHE_TTL = {
  positions: 2000,      // 2 seconds
  orders: 2000,         // 2 seconds
  health: 10000,        // 10 seconds
  news: 60000,          // 60 seconds
  signal: 30000,        // 30 seconds
  workers: 5000,        // 5 seconds
  decisions: 3000,      // 3 seconds
};

const REALTIME = {
  ws: null,
  url: '',
  ticks: {},
  status: 'connecting',
  reconnectTimer: null,
  heartbeatTimer: null,
  reconnectAttempts: 0,
  tickListeners: new Set(),
  statusListeners: new Set(),
};

function getCachedOrFetch(key, fetcher, ttl) {
  const now = Date.now();
  const cached = API_CACHE[key];
  const resolvedTtl = ttl ?? CACHE_TTL[key] ?? 5000;
  
  if (cached && now - cached.timestamp < resolvedTtl) {
    return Promise.resolve(cached.data);
  }

  if (IN_FLIGHT[key]) {
    return IN_FLIGHT[key];
  }
  
  IN_FLIGHT[key] = fetcher().then(data => {
    API_CACHE[key] = { data, timestamp: now };
    return data;
  }).finally(() => {
    delete IN_FLIGHT[key];
  });

  return IN_FLIGHT[key];
}

function prefetchCached(key, fetcher, ttl) {
  const now = Date.now();
  const resolvedTtl = ttl ?? CACHE_TTL[key] ?? 5000;
  const cached = API_CACHE[key];

  if (cached && now - cached.timestamp < resolvedTtl) {
    return Promise.resolve(cached.data);
  }

  return getCachedOrFetch(key, fetcher, resolvedTtl).catch(() => null);
}

function emitStatus(status) {
  REALTIME.status = status;
  REALTIME.statusListeners.forEach(callback => callback(status));
}

function emitTicks(ticks) {
  REALTIME.ticks = ticks;
  REALTIME.tickListeners.forEach(callback => callback(ticks));
}

function scheduleReconnect(BASE, API_KEY) {
  clearTimeout(REALTIME.reconnectTimer);
  const delay = Math.min(10000, 750 * (2 ** Math.min(REALTIME.reconnectAttempts, 4)));
  REALTIME.reconnectAttempts += 1;
  REALTIME.reconnectTimer = setTimeout(() => connectSharedSocket(BASE, API_KEY), delay);
}

function startHeartbeat() {
  clearInterval(REALTIME.heartbeatTimer);
  REALTIME.heartbeatTimer = setInterval(() => {
    if (REALTIME.ws?.readyState === WebSocket.OPEN) {
      REALTIME.ws.send(JSON.stringify({ type: 'ping', ts: Date.now() }));
    }
  }, 25000);
}

function connectSharedSocket(BASE, API_KEY) {
  const url = API_KEY
    ? `${BASE.replace(/^http/, 'ws')}/ws?api_key=${encodeURIComponent(API_KEY)}`
    : `${BASE.replace(/^http/, 'ws')}/ws`;

  if (
    REALTIME.ws &&
    REALTIME.url === url &&
    (REALTIME.ws.readyState === WebSocket.OPEN || REALTIME.ws.readyState === WebSocket.CONNECTING)
  ) {
    return;
  }

  clearTimeout(REALTIME.reconnectTimer);
  emitStatus(REALTIME.reconnectAttempts > 0 ? 'reconnecting' : 'connecting');

  try {
    if (REALTIME.ws && REALTIME.ws.readyState !== WebSocket.CLOSED) {
      REALTIME.ws.close();
    }

    const ws = new WebSocket(url);
    REALTIME.ws = ws;
    REALTIME.url = url;

    ws.onopen = () => {
      REALTIME.reconnectAttempts = 0;
      emitStatus('connected');
      startHeartbeat();
    };

    ws.onmessage = (ev) => {
      try {
        const msg = JSON.parse(ev.data);
        if (msg.type === 'tick_batch' && Array.isArray(msg.data)) {
          const updated = { ...REALTIME.ticks };
          msg.data.forEach(tick => {
            if (tick?.symbol) {
              updated[tick.symbol] = tick;
            }
          });
          emitTicks(updated);
        }
      } catch (e) {
        console.warn('WS parse error', e);
      }
    };

    ws.onerror = (e) => {
      console.warn('WS error', e);
      emitStatus('error');
    };

    ws.onclose = () => {
      clearInterval(REALTIME.heartbeatTimer);
      emitStatus('reconnecting');
      scheduleReconnect(BASE, API_KEY);
    };
  } catch (e) {
    console.error('WebSocket connection failed', e);
    emitStatus('error');
    scheduleReconnect(BASE, API_KEY);
  }
}

export function useRealTimeData() {
  const [ticks, setTicks] = useState(REALTIME.ticks);
  const [wsStatus, setWsStatus] = useState(REALTIME.status);
  const subscribersRef = useRef(new Set());

  const BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
  const API_KEY = import.meta.env.VITE_API_KEY || '';

  useEffect(() => {
    const handleTicks = (nextTicks) => {
      setTicks(nextTicks);
      subscribersRef.current.forEach(callback => callback(nextTicks));
    };
    const handleStatus = (status) => setWsStatus(status);

    REALTIME.tickListeners.add(handleTicks);
    REALTIME.statusListeners.add(handleStatus);
    connectSharedSocket(BASE, API_KEY);

    return () => {
      REALTIME.tickListeners.delete(handleTicks);
      REALTIME.statusListeners.delete(handleStatus);
    };
  }, [BASE, API_KEY]);

  // Subscribe to tick updates
  const subscribeTicks = useCallback((callback) => {
    subscribersRef.current.add(callback);
    return () => subscribersRef.current.delete(callback);
  }, []);

  // Cached fetch wrapper
  const cachedFetch = useCallback((key, fetcher, ttl) => {
    return getCachedOrFetch(key, fetcher, ttl ?? CACHE_TTL[key] ?? 5000);
  }, []);

  const prefetchCache = useCallback((key, fetcher, ttl) => {
    return prefetchCached(key, fetcher, ttl ?? CACHE_TTL[key] ?? 5000);
  }, []);

  // Clear cache
  const clearCache = useCallback((key) => {
    if (key) {
      delete API_CACHE[key];
    } else {
      Object.keys(API_CACHE).forEach(k => delete API_CACHE[k]);
    }
  }, []);

  return {
    ticks,
    wsStatus,
    subscribeTicks,
    cachedFetch,
    prefetchCache,
    clearCache,
  };
}
