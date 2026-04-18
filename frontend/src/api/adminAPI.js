/**
 * Admin, Research & Blog API Client
 * Centralized API calls for the dashboard pages
 */

const BACKEND_BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const API_BASE = `${BACKEND_BASE}/api`;
const FUND_BASE = `${BACKEND_BASE}/fund`;
const PAPER_BASE = `${BACKEND_BASE}/paper`;
const MARKET_BASE = `${BACKEND_BASE}/market`;
const API_KEY = import.meta.env.VITE_API_KEY || "";

function withAuth(options = {}) {
  const headers = {
    ...(options.headers || {}),
    ...(API_KEY ? { "X-API-Key": API_KEY } : {}),
  };
  return { ...options, headers };
}

async function fetchJson(url, options = {}) {
  const res = await fetch(url, withAuth(options));
  if (!res.ok) {
    throw new Error(`Request failed (${res.status}): ${url}`);
  }
  return res.json();
}

function normalizeArray(payload, fieldName) {
  if (Array.isArray(payload)) return payload;
  if (payload && Array.isArray(payload[fieldName])) return payload[fieldName];
  return [];
}

// ============================================================
// ADMIN ENDPOINTS
// ============================================================

export const adminAPI = {
  /**
   * Get dashboard metrics summary
   */
  getMetricsSummary: async () => {
    return fetchJson(`${API_BASE}/admin/metrics/summary`);
  },

  getSystemStatusBadges: async () => {
    return fetchJson(`${API_BASE}/admin/system/status-badges`);
  },
  getRuntimeControlStatus: async () => {
    return fetchJson(`${API_BASE}/admin/system/runtime/control`);
  },
  getRuntimeControlHistory: async (limit = 30) => {
    return fetchJson(`${API_BASE}/admin/system/control-history?limit=${encodeURIComponent(limit)}`);
  },
  pauseRuntime: async (reason = "manual_admin_pause") => {
    return fetchJson(`${API_BASE}/admin/system/runtime/pause`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
  },
  resumeRuntime: async (reason = "manual_admin_resume") => {
    return fetchJson(`${API_BASE}/admin/system/runtime/resume`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
  },
  clearSystemHalt: async (reason = "manual_admin_clear_halt") => {
    return fetchJson(`${API_BASE}/admin/system/halt/clear`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    });
  },
  kickAutopilot: async (runId = "") => {
    return fetchJson(`${API_BASE}/admin/system/autopilot/kick`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ run_id: runId || null }),
    });
  },

  /**
   * Get agent worker pool status
   */
  getAgentsStatus: async () => {
    return fetchJson(`${API_BASE}/admin/agents/workers/status`);
  },

  /**
   * Get active agent tasks
   */
  getActiveTasks: async () => {
    return fetchJson(`${API_BASE}/admin/agents/tasks/active`);
  },

  /**
   * Get pending decisions queue
   */
  getPendingDecisions: async () => {
    return fetchJson(`${API_BASE}/admin/decisions/pending`);
  },

  /**
   * Approve a pending decision
   */
  approveDecision: async (decisionId) => {
    return fetchJson(`${API_BASE}/admin/decisions/${decisionId}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  },

  /**
   * Reject a pending decision
   */
  rejectDecision: async (decisionId) => {
    return fetchJson(`${API_BASE}/admin/decisions/${decisionId}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  },

  /**
   * Get sleeve allocations and budgets
   */
  getSleevesBudgets: async () => {
    return fetchJson(`${API_BASE}/admin/sleeves/budgets`);
  },

  /**
   * Get audit trail for an order
   */
  getOrderAuditTimeline: async (orderId) => {
    return fetchJson(`${API_BASE}/admin/audit/orders/${orderId}/timeline`);
  },
  getRecentLineage: async (limit = 20) => {
    return fetchJson(`${API_BASE}/admin/lineage/recent?limit=${encodeURIComponent(limit)}`);
  },
  getLineageRunDetail: async (runId, limit = 300) => {
    return fetchJson(
      `${API_BASE}/admin/lineage/run/${encodeURIComponent(runId)}?limit=${encodeURIComponent(limit)}`
    );
  },

  // Live fund runtime endpoints
  getFundWorkersStatus: async () => fetchJson(`${FUND_BASE}/agents/workers/status`),
  getFundActiveTasks: async () => fetchJson(`${FUND_BASE}/agents/tasks/active`),
  getFundTaskHistory: async (limit = 30) =>
    fetchJson(`${FUND_BASE}/agents/tasks/history?limit=${encodeURIComponent(limit)}`),
  getFundPendingDecisions: async () => fetchJson(`${FUND_BASE}/decisions/pending`),
  approveFundDecision: async (decisionId) =>
    fetchJson(`${FUND_BASE}/decisions/${decisionId}/approve`, { method: "POST" }),
  rejectFundDecision: async (decisionId) =>
    fetchJson(`${FUND_BASE}/decisions/${decisionId}/reject`, { method: "POST" }),
  getFundSleevesBudgets: async (runId = "") => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return fetchJson(`${FUND_BASE}/sleeves/budgets${query}`);
  },
  getFundBlockedTrades: async (limit = 50) =>
    fetchJson(`${FUND_BASE}/trades/blocked?limit=${encodeURIComponent(limit)}`),
  getFundKnowledgeEvents: async (limit = 50, namespace = "development") =>
    fetchJson(
      `${FUND_BASE}/knowledge/events?limit=${encodeURIComponent(limit)}&namespace=${encodeURIComponent(namespace)}`
    ),
  getFundOrderAuditTimeline: async (orderId) =>
    fetchJson(`${FUND_BASE}/audit/orders/${encodeURIComponent(orderId)}/timeline`),
  getPaperPositions: async () => fetchJson(`${PAPER_BASE}/positions`),
  getMarketPrices: async () => fetchJson(`${MARKET_BASE}/prices`),
  placePaperOrder: async (payload) =>
    fetchJson(`${PAPER_BASE}/order`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),

  normalizeArray,
};

// ============================================================
// RESEARCH ENDPOINTS
// ============================================================

export const researchAPI = {
  /**
   * Get list of research reports
   */
  getReports: async (options = {}) => {
    const params = new URLSearchParams();
    if (options.status) params.append("status", options.status);
    if (options.agentRole) params.append("agent_role", options.agentRole);
    if (options.asset) params.append("asset", options.asset);
    if (options.limit) params.append("limit", options.limit);
    if (options.offset) params.append("offset", options.offset);

    const url = `${API_BASE}/research/reports?${params.toString()}`;
    return fetchJson(url);
  },

  /**
   * Get detailed research report
   */
  getReportDetail: async (reportId) => {
    return fetchJson(`${API_BASE}/research/reports/${reportId}`);
  },

  /**
   * Create/publish a new research report
   */
  createReport: async (report) => {
    return fetchJson(`${API_BASE}/research/reports`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(report),
    });
  },

  /**
   * Get current sentiment data
   */
  getCurrentSentiment: async () => {
    return fetchJson(`${API_BASE}/research/sentiment/current`);
  },

  /**
   * Get sentiment history for a symbol
   */
  getSentimentHistory: async (symbol, days = 30) => {
    return fetchJson(
      `${API_BASE}/research/sentiment/history/${symbol}?days=${days}`
    );
  },
};

// ============================================================
// BLOG ENDPOINTS
// ============================================================

export const blogAPI = {
  /**
   * Get list of blog posts
   */
  getPosts: async (options = {}) => {
    const params = new URLSearchParams();
    if (options.category) params.append("category", options.category);
    if (options.limit) params.append("limit", options.limit);
    if (options.offset) params.append("offset", options.offset);

    const url = `${API_BASE}/blog/posts?${params.toString()}`;
    return fetchJson(url);
  },

  /**
   * Get detailed blog post
   */
  getPostDetail: async (postId) => {
    return fetchJson(`${API_BASE}/blog/posts/${postId}`);
  },
};
