const BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const API_KEY = import.meta.env.VITE_API_KEY || "";

function authHeaders(extra = {}) {
  return {
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
    ...extra,
  };
}

export async function getHealth() {
  const res = await fetch(`${BASE}/health`);
  return res.json();
}

export async function getSignal(symbol) {
  const res = await fetch(`${BASE}/signals/generate`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({ symbol }),
  });
  return res.json();
}

export async function getPositions() {
  const res = await fetch(`${BASE}/paper/positions`, {
    headers: authHeaders(),
  });
  return res.json();
}

export async function getOrders() {
  const res = await fetch(`${BASE}/paper/orders`, {
    headers: authHeaders(),
  });
  return res.json();
}

export async function placeOrder(order) {
  const res = await fetch(`${BASE}/paper/order`, {
    method: "POST",
    headers: authHeaders({ "Content-Type": "application/json" }),
    body: JSON.stringify({
      symbol: order.symbol,
      side: order.side,
      quantity: order.qty ?? order.quantity,
    }),
  });
  return res.json();
}

export function wsConnect(onMessage) {
  const url =
    (API_KEY
      ? BASE.replace(/^http/, "ws") + "/ws?api_key=" + API_KEY
      : BASE.replace(/^http/, "ws") + "/ws");
  const ws = new WebSocket(url);
  ws.onmessage = (ev) => {
    try {
      const msg = JSON.parse(ev.data);
      onMessage?.(msg);
    } catch (e) {
      console.warn("WS parse error", e);
    }
  };
  ws.onerror = (e) => console.warn("WS error", e);
  return ws;
}

export async function getNews(symbol) {
  const res = await fetch(`${BASE}/news/${symbol}`, {
    headers: authHeaders(),
  });
  return res.json();
}

export async function getAnalytics() {
  const res = await fetch(`${BASE}/analytics/summary`, {
    headers: authHeaders(),
  });
  if (!res.ok) throw new Error("analytics fetch failed");
  return res.json();
}