import React from "react";

const ACTIONS = {
  buy: { color: "var(--green)", bg: "rgba(62,207,142,0.08)", border: "rgba(62,207,142,0.2)", label: "BUY" },
  sell: { color: "var(--red)", bg: "rgba(224,82,82,0.08)", border: "rgba(224,82,82,0.2)", label: "SELL" },
  hold: { color: "var(--txt2)", bg: "rgba(139,145,158,0.06)", border: "rgba(139,145,158,0.15)", label: "HOLD" },
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
          <div style={{ gridColumn: "1 / -1", marginTop: 2, display: "grid", gap: 4 }}>
            <div className="label" style={{ fontSize: 8 }}>Core Engine Diagnostics</div>
            <div style={{ fontFamily: "var(--f-data)", fontSize: 9, color: "var(--txt2)" }}>
              MODEL {modelVersion} | CONTRACT {shortHash(contractHash)}
            </div>
            <div style={{ fontFamily: "var(--f-data)", fontSize: 9, color: safeMode ? "var(--amber)" : "var(--teal)" }}>
              POLICY {safeMode ? "SAFE_MODE_HOLD" : "ACTIVE"} {rejections.length ? `| ${rejections.join(", ")}` : ""}
            </div>
            {!!reasonCodes.length && (
              <div style={{ fontFamily: "var(--f-data)", fontSize: 9, color: "var(--txt3)" }}>
                REASONS {reasonCodes.slice(0, 4).join(", ")}
              </div>
            )}
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

