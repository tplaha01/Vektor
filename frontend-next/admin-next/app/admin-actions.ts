"use server";

import { revalidatePath } from "next/cache";
import { postJson } from "@/lib/admin-api";

const allowedActions: Record<string, { path: string; body?: Record<string, unknown> }> = {
  pause: {
    path: "/api/admin/system/runtime/pause",
    body: { reason: "manual_admin_pause" },
  },
  resume: {
    path: "/api/admin/system/runtime/resume",
    body: { reason: "manual_admin_resume" },
  },
  clear_halt: {
    path: "/api/admin/system/halt/clear",
    body: { reason: "manual_admin_clear_halt" },
  },
  autopilot_kick: { path: "/api/admin/system/autopilot/kick" },
  functional_verify: {
    path: "/api/admin/system/functional/verify",
    body: { symbol: "SPY" },
  },
  data_integrity_drill: {
    path: "/api/admin/system/data-integrity/drill",
    body: {
      provider: "manual_operator_check",
      mode: "provider",
      symbol: "SPY",
      detail: "operator_data_integrity_check",
      reason: "operator_data_integrity_check",
    },
  },
  deterministic_recover: {
    path: "/api/admin/system/deterministic-ml/recover",
    body: { reason: "manual_admin_deterministic_recover" },
  },
};

export async function runAdminAction(formData: FormData) {
  const action = String(formData.get("action") || "");
  const config = allowedActions[action];

  if (!config) {
    throw new Error(`Unsupported admin action: ${action}`);
  }

  await postJson(config.path, config.body);
  revalidatePath("/");
}

export async function updatePaperBrokerCapital(formData: FormData) {
  const amount = Number(formData.get("amount_usd") || formData.get("delta_usd") || 0);
  const reason = String(formData.get("reason") || "operator_adjustment");

  if (!Number.isFinite(amount) || amount <= 0) {
    throw new Error("amount_usd must be a positive finite number");
  }

  await postJson("/api/admin/system/paper-broker/capital", {
    action: "top_up",
    amount_usd: amount,
    reason,
  });
  revalidatePath("/");
}
