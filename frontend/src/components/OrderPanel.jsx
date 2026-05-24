import React, { useState } from "react";

const panelTone = (receipt) => {
  if (!receipt) return { border: "var(--line)", bg: "rgba(255,255,255,0.02)", text: "var(--txt2)" };
  if (receipt.ok) return { border: "rgba(62,207,142,0.28)", bg: "rgba(62,207,142,0.08)", text: "var(--green)" };
  return { border: "rgba(224,82,82,0.28)", bg: "rgba(224,82,82,0.08)", text: "var(--red)" };
};

const REASON_LABELS = {
  backend_unreachable: "backend link",
  system_halted: "runtime halted",
  confidence_below_threshold: "confidence",
  expected_utility_below_threshold: "utility",
  fundamentals_timestamp_missing: "fresh fundamentals",
  stale_market_data: "market data",
  low_confidence: "low confidence",
  ml_score_below_threshold: "ml score",
  policy_confidence_below_threshold: "policy confidence",
  policy_expected_utility_below_threshold: "policy utility",
};

const humanizeReason = (value) => {
  const key = String(value || "").trim().toLowerCase();
  if (!key) return "";
  return REASON_LABELS[key] || key.replace(/_/g, " ");
};

const summarizeError = (error) => {
  const networkFailure = String(error?.message || "").toLowerCase() === "failed to fetch";
  const detail = error?.detail && typeof error.detail === "object"
    ? error.detail
    : error?.payload?.detail && typeof error.payload.detail === "object"
      ? error.payload.detail
      : null;
  const reasons = Array.isArray(detail?.reasons)
    ? detail.reasons
    : [detail?.reason || detail?.error || (networkFailure ? "backend_unreachable" : error?.message)].filter(Boolean);
  return {
    ok: false,
    title: networkFailure ? "Backend unreachable" : detail?.error === "system_halted" ? "Runtime halted" : "Order blocked",
    summary: networkFailure
      ? "Paper order could not reach the backend. The order was not submitted."
      : detail?.message || error?.message || "Paper order failed.",
    reasons,
    runId: detail?.run_id || error?.payload?.run_id || null,
    decisionId: detail?.decision_id || error?.payload?.decision_id || null,
    riskId: detail?.risk_id || error?.payload?.risk_id || null,
    intentId: detail?.intent_id || error?.payload?.intent_id || null,
    orderId: null,
  };
};

const summarizeResult = (result) => {
  if (!result || result.approved === false) {
    return {
      ok: false,
      title: "Order blocked",
      summary: result?.error || "Manual order was blocked by the core policy gate.",
      reasons: Array.isArray(result?.reasons) ? result.reasons : [result?.error].filter(Boolean),
      runId: result?.run_id || null,
      decisionId: result?.decision_id || null,
      riskId: result?.risk_id || null,
      intentId: result?.intent_id || null,
      orderId: result?.id || null,
    };
  }
  return {
    ok: true,
    title: "Order accepted",
    summary: `${String(result.side || "").toUpperCase()} ${result.quantity} ${result.symbol} routed into paper execution.`,
    reasons: [],
    runId: result?.run_id || null,
    decisionId: result?.decision_id || null,
    riskId: result?.risk_id || null,
    intentId: result?.intent_id || null,
    orderId: result?.id || null,
  };
};

const idRows = (receipt) => ([
  ["Run", receipt?.runId],
  ["Decision", receipt?.decisionId],
  ["Risk", receipt?.riskId],
  ["Intent", receipt?.intentId],
  ["Order", receipt?.orderId],
]).filter(([, value]) => Boolean(value));

const reasonTags = (receipt) =>
  Array.from(new Set((Array.isArray(receipt?.reasons) ? receipt.reasons : []).map(humanizeReason).filter(Boolean))).slice(0, 4);

export default function OrderPanel({ symbol, onPlace }) {
  const [side, setSide] = useState("buy");
  const [qty, setQty] = useState("1");
  const [busy, setBusy] = useState(false);
  const [receipt, setReceipt] = useState(null);

  const submit = async () => {
    setBusy(true);
    setReceipt(null);
    try {
      const result = await onPlace({ symbol, side, quantity: parseFloat(qty) || 1 });
      setReceipt(summarizeResult(result));
    } catch (error) {
      setReceipt(summarizeError(error));
    } finally {
      setBusy(false);
    }
  };

  const tone = panelTone(receipt);

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", gap: 8 }}>
        <span className="label">Quick Order</span>
        <div style={{ display: "flex", gap: 6, flexWrap: "wrap", justifyContent: "flex-end" }}>
          {["paper only", "policy gate"].map((badge) => (
            <span
              key={badge}
              style={{
                padding: "2px 7px",
                borderRadius: 999,
                border: "1px solid rgba(255,255,255,0.08)",
                fontFamily: "var(--f-data)",
                fontSize: 8,
                color: "var(--txt3)",
                letterSpacing: "0.08em",
                textTransform: "uppercase",
              }}
            >
              {badge}
            </span>
          ))}
        </div>
      </div>

      <div style={{
        padding: "8px 10px",
        borderRadius: "var(--r-sm)",
        border: "1px solid rgba(255,255,255,0.06)",
        background: "rgba(255,255,255,0.02)",
        color: "var(--txt2)",
        fontSize: 11,
        lineHeight: 1.5,
      }}>
        Manual orders inherit the same deterministic policy contract used by orchestrated paper execution.
      </div>

      <div style={{ display: "flex", gap: 4 }}>
        {["buy", "sell"].map((option) => (
          <button
            key={option}
            className="btn-side"
            onClick={() => setSide(option)}
            style={{
              background: side === option ? (option === "buy" ? "var(--green)" : "var(--red)") : "var(--bg3)",
              color: side === option ? (option === "buy" ? "#001a0d" : "#150000") : "var(--txt3)",
              border: side === option ? "none" : "1px solid var(--line)",
            }}
          >
            {option.toUpperCase()}
          </button>
        ))}
      </div>

      <div style={{ display: "flex", gap: 6 }}>
        <div
          style={{
            flex: 1,
            background: "var(--bg3)",
            border: "1px solid var(--line)",
            borderRadius: "var(--r-sm)",
            padding: "6px 8px",
            fontFamily: "var(--f-data)",
            fontSize: 11,
            color: "var(--txt2)",
            letterSpacing: "0.06em",
          }}
        >
          {symbol}
        </div>
        <input
          type="number"
          min="1"
          value={qty}
          onChange={(event) => setQty(event.target.value)}
          className="inp"
          style={{ width: 60, textAlign: "center", textTransform: "none" }}
        />
      </div>

      <button className="btn btn-amber" onClick={submit} disabled={busy} style={{ width: "100%" }}>
        {busy ? "Submitting..." : `${side === "buy" ? "Buy" : "Sell"} ${qty}`}
      </button>

      {receipt ? (
        <div
          style={{
            display: "flex",
            flexDirection: "column",
            gap: 8,
            borderRadius: "var(--r)",
            border: `1px solid ${tone.border}`,
            background: tone.bg,
            padding: "10px",
          }}
        >
          <div style={{ display: "flex", justifyContent: "space-between", gap: 8, alignItems: "center" }}>
            <strong style={{ fontSize: 11, letterSpacing: "0.08em", textTransform: "uppercase", color: tone.text }}>
              {receipt.title}
            </strong>
            <span style={{ fontFamily: "var(--f-data)", fontSize: 9, color: "var(--txt3)" }}>
              {receipt.ok ? "approved" : receipt.title === "Backend unreachable" ? "offline" : "blocked"}
            </span>
          </div>

          <div style={{ color: "var(--txt)", fontSize: 12, lineHeight: 1.5 }}>
            {receipt.summary}
          </div>

          {reasonTags(receipt).length ? (
            <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
              {reasonTags(receipt).map((reason) => (
                <span
                  key={reason}
                  style={{
                    padding: "4px 6px",
                    borderRadius: 999,
                    border: `1px solid ${tone.border}`,
                    fontFamily: "var(--f-data)",
                    fontSize: 9,
                    color: tone.text,
                    letterSpacing: "0.06em",
                  }}
                >
                  {reason}
                </span>
              ))}
            </div>
          ) : null}

          {idRows(receipt).length ? (
            <div style={{ display: "grid", gridTemplateColumns: "auto 1fr", gap: "4px 8px", fontSize: 10 }}>
              {idRows(receipt).map(([label, value]) => (
                <React.Fragment key={label}>
                  <span style={{ color: "var(--txt3)", textTransform: "uppercase", letterSpacing: "0.08em" }}>{label}</span>
                  <span style={{ color: "var(--txt2)", fontFamily: "var(--f-data)", overflow: "hidden", textOverflow: "ellipsis" }}>{value}</span>
                </React.Fragment>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
