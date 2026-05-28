import { useEffect, useRef, useState, useCallback } from 'react';

const API_CACHE = {};
const CACHE_TTL = {
  positions: 2000,      // 2 seconds
  orders: 2000,         // 2 seconds
  health: 10000,        // 10 seconds
  news: 60000,          // 60 seconds
  signal: 30000,        // 30 seconds
  workers: 5000,        // 5 seconds
  decisions: 3000,      // 3 seconds
};

function getCachedOrFetch(key, fetcher, ttl) {
  const now = Date.now();
  const cached = API_CACHE[key];
  
  if (cached && now - cached.timestamp < ttl) {
    return Promise.resolve(cached.data);
  }
  
  return fetcher().then(data => {
    API_CACHE[key] = { data, timestamp: now };
    return data;
  });
}

export function useRealTimeData() {
  const wsRef = useRef(null);
  const [ticks, setTicks] = useState({});
  const [wsStatus, setWsStatus] = useState('connecting');
  const subscribersRef = useRef(new Set());

  const BASE = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
  const API_KEY = import.meta.env.VITE_API_KEY || '';

  // Establish WebSocket connection
  useEffect(() => {
    let reconnectTimeout;
    
    const connect = () => {
      try {
        const url = API_KEY
          ? BASE.replace(/^http/, 'ws') + '/ws?api_key=' + API_KEY
          : BASE.replace(/^http/, 'ws') + '/ws';
        
        const ws = new WebSocket(url);
        
        ws.onopen = () => {
          console.log('WebSocket connected');
          setWsStatus('connected');
        };
        
        ws.onmessage = (ev) => {
          try {
            const msg = JSON.parse(ev.data);
            if (msg.type === 'tick_batch' && msg.data) {
              setTicks(prev => {
                const updated = { ...prev };
                msg.data.forEach(tick => {
                  updated[tick.symbol] = tick;
                });
                // Notify all subscribers
                subscribersRef.current.forEach(callback => {
                  callback(updated);
                });
                return updated;
              });
            }
          } catch (e) {
            console.warn('WS parse error', e);
          }
        };
        
        ws.onerror = (e) => {
          console.warn('WS error', e);
          setWsStatus('error');
        };
        
        ws.onclose = () => {
          console.log('WebSocket disconnected');
          setWsStatus('reconnecting');
          reconnectTimeout = setTimeout(connect, 1000);
        };
        
        wsRef.current = ws;
      } catch (e) {
        console.error('WebSocket connection failed', e);
        reconnectTimeout = setTimeout(connect, 1000);
      }
    };
    
    connect();
    
    return () => {
      clearTimeout(reconnectTimeout);
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, [BASE, API_KEY]);

  // Subscribe to tick updates
  const subscribeTicks = useCallback((callback) => {
    subscribersRef.current.add(callback);
    return () => subscribersRef.current.delete(callback);
  }, []);

  // Cached fetch wrapper
  const cachedFetch = useCallback((key, fetcher, ttl = 5000) => {
    return getCachedOrFetch(key, fetcher, ttl || CACHE_TTL[key] || 5000);
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
    clearCache,
  };
}
