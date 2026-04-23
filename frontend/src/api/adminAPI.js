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
    let detail = "";
    try {
      const contentType = String(res.headers.get("content-type") || "").toLowerCase();
      if (contentType.includes("application/json")) {
        const payload = await res.json();
        detail = payload?.detail || payload?.message || JSON.stringify(payload);
      } else {
        detail = (await res.text()) || "";
      }
    } catch {
      detail = "";
    }
    const suffix = detail ? ` - ${String(detail).slice(0, 220)}` : "";
    throw new Error(`Request failed (${res.status}): ${url}${suffix}`);
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
  resetCleanInception: async (payload = {}) => {
    return fetchJson(`${API_BASE}/admin/system/inception/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        starting_cash_usd: payload.startingCashUsd ?? 100000,
        reason: payload.reason || "clean_inception_reset",
      }),
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
  getAllocationPolicy: async (runId = "") => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return fetchJson(`${API_BASE}/admin/allocation/policy${query}`);
  },
  updateAllocationPolicy: async (payload) =>
    fetchJson(`${API_BASE}/admin/allocation/policy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getDiscoveryOpportunities: async ({ limit = 100, runId = "", status = "", assetClass = "" } = {}) => {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (runId) params.set("run_id", runId);
    if (status) params.set("status", status);
    if (assetClass) params.set("asset_class", assetClass);
    return fetchJson(`${API_BASE}/admin/discovery/opportunities?${params.toString()}`);
  },
  getOperatorCrm: async ({ taskLimit = 60, opportunityLimit = 40 } = {}) => {
    const params = new URLSearchParams();
    params.set("task_limit", String(taskLimit));
    params.set("opportunity_limit", String(opportunityLimit));
    return fetchJson(`${API_BASE}/admin/operator/crm?${params.toString()}`);
  },
  getCeoDigest: async () => fetchJson(`${API_BASE}/admin/ceo/digest`),
  getCeoPositionBrief: async (symbol) => fetchJson(`${API_BASE}/admin/ceo/position/${encodeURIComponent(symbol)}`),
  getCeoPerformanceBreakdown: async () => fetchJson(`${API_BASE}/admin/ceo/performance-breakdown`),
  getCeoPositions: async () => fetchJson(`${API_BASE}/admin/ceo/positions`),
  getCeoWinnersLosers: async () => fetchJson(`${API_BASE}/admin/ceo/winners-losers`),
  getCeoExposure: async () => fetchJson(`${API_BASE}/admin/ceo/exposure`),
  getCeoRiskAlerts: async () => fetchJson(`${API_BASE}/admin/ceo/risk-alerts`),
  getCeoCommandHelp: async () => fetchJson(`${API_BASE}/admin/ceo/command-help`),
  getCeoDigests: async (limit = 20, digestType = "") => {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (digestType) params.set("digest_type", digestType);
    return fetchJson(`${API_BASE}/admin/ceo/digests?${params.toString()}`);
  },
  generateCeoDigest: async () =>
    fetchJson(`${API_BASE}/admin/ceo/digest/generate`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    }),
  getPendingApprovals: async (limit = 50, requestType = "") => {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (requestType) params.set("request_type", requestType);
    return fetchJson(`${API_BASE}/admin/ceo/approvals/pending?${params.toString()}`);
  },
  getApprovalDetail: async (requestId) => fetchJson(`${API_BASE}/admin/ceo/approvals/${encodeURIComponent(requestId)}`),
  approveRequest: async (requestId, notes = "Approved by CEO in admin") =>
    fetchJson(`${API_BASE}/admin/ceo/approvals/${encodeURIComponent(requestId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes }),
    }),
  rejectRequest: async (requestId, notes = "Rejected by CEO in admin") =>
    fetchJson(`${API_BASE}/admin/ceo/approvals/${encodeURIComponent(requestId)}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ notes }),
    }),
  getPendingEditorial: async () => fetchJson(`${API_BASE}/admin/ceo/editorial/pending`),
  getEditorialDetail: async (postId) => fetchJson(`${API_BASE}/admin/ceo/editorial/${encodeURIComponent(postId)}`),
  approveEditorial: async (postId, reason = "Approved by CEO") =>
    fetchJson(`${API_BASE}/admin/ceo/editorial/${encodeURIComponent(postId)}/approve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }),
  rejectEditorial: async (postId, reason = "Changes requested by CEO") =>
    fetchJson(`${API_BASE}/admin/ceo/editorial/${encodeURIComponent(postId)}/reject`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reason }),
    }),
  getMarketWatch: async () => fetchJson(`${API_BASE}/admin/ceo/market-watch`),

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
  getFundAllocationPolicy: async (runId = "") => {
    const query = runId ? `?run_id=${encodeURIComponent(runId)}` : "";
    return fetchJson(`${FUND_BASE}/allocation/policy${query}`);
  },
  updateFundAllocationPolicy: async (payload) =>
    fetchJson(`${FUND_BASE}/allocation/policy`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    }),
  getFundDiscoveryOpportunities: async ({ limit = 100, runId = "", status = "", assetClass = "" } = {}) => {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (runId) params.set("run_id", runId);
    if (status) params.set("status", status);
    if (assetClass) params.set("asset_class", assetClass);
    return fetchJson(`${FUND_BASE}/discovery/opportunities?${params.toString()}`);
  },
  getFundBlockedTrades: async (limit = 50) =>
    fetchJson(`${FUND_BASE}/trades/blocked?limit=${encodeURIComponent(limit)}`),
  getFundKnowledgeEvents: async (limit = 50, namespace = "development") =>
    fetchJson(
      `${FUND_BASE}/knowledge/events?limit=${encodeURIComponent(limit)}&namespace=${encodeURIComponent(namespace)}`
    ),
  getPerformanceSummary: async () => fetchJson(`${FUND_BASE}/performance/summary`),
  getPerformanceSnapshots: async ({ limit = 180, snapshotKind = "", startAt = "", endAt = "" } = {}) => {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    if (snapshotKind) params.set("snapshot_kind", snapshotKind);
    if (startAt) params.set("start_at", startAt);
    if (endAt) params.set("end_at", endAt);
    return fetchJson(`${FUND_BASE}/performance/snapshots?${params.toString()}`);
  },
  capturePerformanceSnapshot: async (payload = {}) =>
    fetchJson(`${FUND_BASE}/performance/capture`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        snapshot_kind: payload.snapshotKind || "manual",
        reason: payload.reason || "manual_admin_checkpoint",
      }),
    }),
  resetPerformanceHistory: async () =>
    fetchJson(`${FUND_BASE}/performance/reset`, {
      method: "POST",
    }),
  getFundOrderAuditTimeline: async (orderId) =>
    fetchJson(`${FUND_BASE}/audit/orders/${encodeURIComponent(orderId)}/timeline`),
  getKnowledgeStats: async () => fetchJson(`${API_BASE}/knowledge/stats`),
  resetKnowledgeBase: async (payload = {}) =>
    fetchJson(`${API_BASE}/knowledge/reset`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_id: payload.run_id || null,
        agent_id: payload.agent_id || "ceo",
        seed_event: payload.seed_event ?? false,
      }),
    }),
  rebuildKnowledgeProjection: async (payload = {}) =>
    fetchJson(`${API_BASE}/knowledge/rebuild`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        run_id: payload.run_id || null,
        agent_id: payload.agent_id || "ceo",
        seed_event: payload.seed_event ?? false,
      }),
    }),
  
  // Agent Hierarchy & Orchestration
  getAgentHierarchy: async () =>
    fetchJson(`${API_BASE}/monitor/agents/hierarchy`),
  getAgentHierarchyStats: async () =>
    fetchJson(`${API_BASE}/monitor/agents/hierarchy/stats`),
  
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
    if (options.surface) params.append("surface", options.surface);
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
    if (options.status) params.append("status", options.status);
    if (options.limit) params.append("limit", options.limit);
    if (options.offset) params.append("offset", options.offset);

    const url = `${API_BASE}/blog/posts?${params.toString()}`;
    const payload = await fetchJson(url);
    if (payload && Array.isArray(payload.blogs) && !Array.isArray(payload.posts)) {
      return { ...payload, posts: payload.blogs };
    }
    return payload;
  },

  /**
   * Get detailed blog post
   */
  getPostDetail: async (postId) => {
    return fetchJson(`${API_BASE}/blog/posts/${postId}`);
  },
};
