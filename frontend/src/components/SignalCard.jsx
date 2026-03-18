import React from "react"

const ACTIONS = {
  buy:  { color:"var(--green)",  bg:"rgba(62,207,142,0.08)",  border:"rgba(62,207,142,0.2)",  label:"BUY"  },
  sell: { color:"var(--red)",    bg:"rgba(224,82,82,0.08)",   border:"rgba(224,82,82,0.2)",   label:"SELL" },
  hold: { color:"var(--txt2)",   bg:"rgba(139,145,158,0.06)", border:"rgba(139,145,158,0.15)", label:"HOLD" },
}

const REGIME_C = {
  TREND_UP:"var(--green)", TREND_DOWN:"var(--red)", BREAKOUT_UP:"var(--teal)",
  BREAKOUT_DOWN:"#fb923c", RANGE:"var(--amber)", HIGH_VOL:"var(--purple)",
}

function Bar({ label, value }) {
  const v = value ?? 0;
  const pct = Math.min(Math.abs(v)*100, 100);
  const col = v >= 0 ? "var(--green)" : "var(--red)";
  return (
    <div>
      <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
        <span className="label" style={{ fontSize:8 }}>{label}</span>
        <span style={{ fontFamily:"var(--f-data)", fontSize:10, color:col }}>
          {v>=0?"+":""}{v.toFixed(3)}
        </span>
      </div>
      <div className="bar-track">
        <div className="bar-fill" style={{ width:`${pct}%`, background:col }} />
      </div>
    </div>
  );
}

export default function SignalCard({ signal, symbol, tick }) {
  const a = ACTIONS[signal?.action ?? "hold"] ?? ACTIONS.hold;
  const score = signal?.score ?? 0;
  const sub   = signal?.subscores ?? {};
  const mlOk  = signal?.ml_ready ?? false;
  const sent  = signal?.sentiment_model ?? "VADER";
  const chg   = tick?.change ?? 0;

  return (
    <div className="panel" style={{ background:a.bg, borderColor:a.border }}>
      <div style={{ display:"grid", gridTemplateColumns:"auto 1fr auto", gap:16, padding:"12px 16px", alignItems:"center" }}>

        {/* Action + Score */}
        <div style={{ minWidth:100 }}>
          <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:4 }}>
            <div className="dot-live" style={{ background:a.color }} />
            <span style={{ fontFamily:"var(--f-data)", fontSize:10, fontWeight:700,
              letterSpacing:"0.2em", color:a.color }}>{a.label}</span>
            <span style={{ fontFamily:"var(--f-data)", fontSize:8, padding:"1px 6px",
              borderRadius:3, border:`1px solid ${mlOk?"var(--teal)":"var(--txt3)"}`,
              color: mlOk?"var(--teal)":"var(--txt3)" }}>
              {mlOk?"LGBM":"MODEL…"}
            </span>
          </div>
          <div style={{ fontFamily:"var(--f-data)", fontSize:32, fontWeight:700,
            color:a.color, letterSpacing:"-0.02em", lineHeight:1 }}>
            {score>=0?"+":""}{score.toFixed(3)}
          </div>
          {signal?.volatility != null && (
            <div style={{ fontFamily:"var(--f-data)", fontSize:9, marginTop:4,
              color: signal.volatility>0.035?"var(--amber)":"var(--txt3)" }}>
              ATR {(signal.volatility*100).toFixed(2)}%{signal.volatility>0.035?" ⚑":""}
            </div>
          )}
        </div>

        {/* Sub-score bars */}
        <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:"8px 24px" }}>
          <Bar label="Technical"   value={sub.technical} />
          <Bar label="Fundamental" value={sub.fundamental} />
          <Bar label="Sentiment"   value={sub.sentiment} />
          <Bar label="ML Alpha"    value={sub.ml_alpha} />
        </div>

        {/* Price summary */}
        {tick && (
          <div style={{ textAlign:"right", minWidth:80 }}>
            <div style={{ fontFamily:"var(--f-data)", fontSize:18, fontWeight:600 }}>
              ${tick.price?.toFixed(2)}
            </div>
            <div style={{ fontFamily:"var(--f-data)", fontSize:11, marginTop:2,
              color: chg>=0?"var(--green)":"var(--red)" }}>
              {chg>=0?"▲":"▼"} {Math.abs(chg).toFixed(2)}%
            </div>
            <div style={{ fontFamily:"var(--f-data)", fontSize:9, marginTop:2, color:"var(--txt3)" }}>
              {sent}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}