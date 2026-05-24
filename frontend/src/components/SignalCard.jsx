import React from "react";

const ACTIONS = {
  buy: { color: "var(--green)", bg: "rgba(62,207,142,0.08)", border: "rgba(62,207,142,0.2)", label: "BUY" },
  sell: { color: "var(--red)", bg: "rgba(224,82,82,0.08)", border: "rgba(224,82,82,0.2)", label: "SELL" },
  hold: { color: "var(--txt2)", bg: "rgba(139,145,158,0.06)", border: "rgba(139,145,158,0.15)", label: "HOLD" },
};

const REASON_LABELS = {
  confidence_below_threshold: "confidence",
  expected_utility_below_threshold: "utility",
  fundamentals_timestamp_missing: "fresh fundamentals",
  stale_market_data: "fresh market data",
  dominant_fundamental: "fundamental tilt",
  low_confidence: "low confidence",
  policy_confidence_below_threshold: "policy confidence",
  policy_expected_utility_below_threshold: "policy utility",
  ml_score_below_threshold: "ml score",
  market_data_stale: "market data",
};

function Bar({ label, value }) {
  const v = Number(value || 0);
  const pct = Math.min(Math.abs(v) * 100, 100);
  const col = v >= 0 ? "var(--green)" : "var(--red)";
  return (
    <div>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 4 }}>
        <span className="label" style={{ fontSize: 8 }}>{label}</span>
        <span style={{ fontFamily: "var(--f-data)", fontSize: 10, color: col }}>
          {v >= 0 ? "+" : ""}{v.toFixed(3)}
        </span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width: `${pct}%`, background: col }} />
      </div>
    </div>
  );
}

function shortHash(value) {
  const text = String(value || "").trim();
  if (!text) return "n/a";
  if (text.length <= 16) return text;
  return `${text.slice(0, 8)}...${text.slice(-8)}`;
}

function formatReason(value) {
  const key = String(value || "").trim().toLowerCase();
  if (!key) return "";
  return REASON_LABELS[key] || key.replace(/_/g, " ");
}

function reasonSummary(values) {
  const items = Array.from(new Set(values.map(formatReason).filter(Boolean)));
  if (!items.length) return "Deterministic contract is clear for this symbol.";
  const focus = items.slice(0, 3).join(", ");
  return `Contract is holding for ${focus}${items.length > 3 ? ", and other guardrails" : ""}.`;
}

export default function SignalCard({ signal, symbol, tick }) {
  const a = ACTIONS[signal?.action ?? "hold"] ?? ACTIONS.hold;
  const score = Number(signal?.score || 0);
  const confidence = Number(signal?.confidence || 0);
  const sub = signal?.subscores ?? {};
  const model = signal?.model ?? {};
  const diagnostics = signal?.diagnostics ?? {};
  const policy = diagnostics?.policy ?? {};
  const reasonCodes = Array.isArray(diagnostics?.reason_codes) ? diagnostics.reason_codes : [];
  const profile = diagnostics?.profile || model?.profile || "balanced";
  const modelVersion = diagnostics?.model_versions?.meta_intent || model?.selected || "meta-intent-v1";
  const contractHash = diagnostics?.determinism?.contract_hash;
  const chg = Number(tick?.change || 0);
  const volatility = Number(signal?.volatility || diagnostics?.technical?.atr_pct || 0);
  const volatilityWarn = volatility > 0.035;
  const rejections = Array.isArray(policy?.rejections) ? policy.rejections : [];
  const safeMode = Boolean(policy?.safe_mode);
  const policyReasons = Array.from(new Set([...rejections, ...reasonCodes].filter(Boolean)));
  const policyBadges = policyReasons.slice(0, 4).map(formatReason).filter(Boolean);
  const policyState = safeMode ? "Safe hold" : policyReasons.length ? "Guarded" : "Clear";
  const policyText = reasonSummary(policyReasons);

  return (
    <div className="panel" style={{ background: a.bg, borderColor: a.border }}>
      <div style={{ display: "grid", gridTemplateColumns: "auto 1fr auto", gap: 16, padding: "12px 16px", alignItems: "center" }}>
        <div style={{ minWidth: 116 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 4 }}>
            <div className="dot-live" style={{ background: a.color }} />
            <span style={{ fontFamily: "var(--f-data)", fontSize: 10, fontWeight: 700, letterSpacing: "0.2em", color: a.color }}>{a.label}</span>
            <span style={{
              fontFamily: "var(--f-data)",
              fontSize: 8,
              padding: "1px 6px",
              borderRadius: 3,
              border: `1px solid ${model?.ready ? "var(--teal)" : "var(--txt3)"}`,
              color: model?.ready ? "var(--teal)" : "var(--txt3)",
            }}>
              {model?.ready ? "CORE READY" : "CORE HOLD"}
            </span>
          </div>
          <div style={{ fontFamily: "var(--f-data)", fontSize: 32, fontWeight: 700, color: a.color, letterSpacing: "-0.02em", lineHeight: 1 }}>
            {score >= 0 ? "+" : ""}{score.toFixed(3)}
          </div>
          <div style={{ fontFamily: "var(--f-data)", fontSize: 10, marginTop: 4, color: "var(--txt2)" }}>
            CONF {(confidence * 100).toFixed(1)}% | {String(profile).toUpperCase()}
          </div>
          <div style={{ fontFamily: "var(--f-data)", fontSize: 9, marginTop: 4, color: volatilityWarn ? "var(--amber)" : "var(--txt3)" }}>
            ATR {(volatility * 100).toFixed(2)}%{volatilityWarn ? " HIGH VOL" : ""}
          </div>
        </div>

        <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: "8px 24px" }}>
          <Bar label="Technical" value={sub.technical} />
          <Bar label="Fundamental" value={sub.fundamental} />
          <Bar label="Sentiment" value={sub.sentiment} />
          <Bar label="Meta Intent" value={sub.ml_alpha ?? sub.ml} />
          <div style={{ gridColumn: "1 / -1", marginTop: 4, display: "grid", gap: 6 }}>
            <div className="label" style={{ fontSize: 8 }}>Core Engine Brief</div>
            <div style={{ fontFamily: "var(--f-ui)", fontSize: 12, lineHeight: 1.45, color: "var(--txt)" }}>
              {policyText}
            </div>
            {policyBadges.length ? (
              <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
                {policyBadges.map((reason) => (
                  <span
                    key={reason}
                    style={{
                      padding: "3px 7px",
                      borderRadius: 999,
                      border: `1px solid ${safeMode ? "rgba(245,166,35,0.24)" : "rgba(255,255,255,0.1)"}`,
                      fontFamily: "var(--f-data)",
                      fontSize: 9,
                      letterSpacing: "0.05em",
                      color: safeMode ? "var(--amber)" : "var(--txt2)",
                    }}
                  >
                    {reason}
                  </span>
                ))}
              </div>
            ) : null}
            <div style={{ display: "grid", gridTemplateColumns: "repeat(3, minmax(0, 1fr))", gap: 8 }}>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "var(--r-sm)", padding: "8px 10px" }}>
                <div className="label" style={{ fontSize: 8, marginBottom: 4 }}>Profile</div>
                <div style={{ fontFamily: "var(--f-data)", fontSize: 10, color: "var(--txt)" }}>{String(profile).toUpperCase()}</div>
              </div>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "var(--r-sm)", padding: "8px 10px" }}>
                <div className="label" style={{ fontSize: 8, marginBottom: 4 }}>Policy</div>
                <div style={{ fontFamily: "var(--f-data)", fontSize: 10, color: safeMode ? "var(--amber)" : "var(--teal)" }}>{policyState}</div>
              </div>
              <div style={{ background: "rgba(255,255,255,0.03)", border: "1px solid rgba(255,255,255,0.06)", borderRadius: "var(--r-sm)", padding: "8px 10px" }}>
                <div className="label" style={{ fontSize: 8, marginBottom: 4 }}>Contract</div>
                <div style={{ fontFamily: "var(--f-data)", fontSize: 10, color: "var(--txt2)" }}>{shortHash(contractHash)}</div>
              </div>
            </div>
            <div style={{ fontFamily: "var(--f-data)", fontSize: 9, color: "var(--txt3)" }}>
              MODEL {modelVersion}
            </div>
          </div>
        </div>

        {tick && (
          <div style={{ textAlign: "right", minWidth: 90 }}>
            <div style={{ fontFamily: "var(--f-data)", fontSize: 18, fontWeight: 600 }}>
              ${Number(tick.price || 0).toFixed(2)}
            </div>
            <div style={{ fontFamily: "var(--f-data)", fontSize: 11, marginTop: 2, color: chg >= 0 ? "var(--green)" : "var(--red)" }}>
              {chg >= 0 ? "UP" : "DOWN"} {Math.abs(chg).toFixed(2)}%
            </div>
            <div style={{ fontFamily: "var(--f-data)", fontSize: 9, marginTop: 2, color: "var(--txt3)" }}>
              {symbol || signal?.symbol || "N/A"}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

