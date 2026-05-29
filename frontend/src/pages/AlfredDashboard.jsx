import React, { useEffect, useState, useCallback } from "react";
import { getSignal, getPositions, placeOrder, wsConnect, getNews, getHealth } from "../api";
import { useRealTimeData } from "../hooks/useRealTimeData";
import { useLivePnL } from "../hooks/useLivePnL";
import SignalCard    from "../components/SignalCard";
import OrderPanel   from "../components/OrderPanel";
import Positions    from "../components/Positions";
import NewsFeed     from "../components/NewsFeed";
import TradingViewWidget from "../components/TradingViewWidget";
import RiskDashboard     from "../components/RiskDashboard";
import BacktestPanel     from "../components/BacktestPanel";
import StrategyDashboard from "../components/StrategyDashboard";
import OpsPanel          from "../components/OpsPanel";

const TABS = [
  { k:"chart",    l:"Chart"     },
  { k:"backtest", l:"Backtest"  },
  { k:"risk",     l:"Risk"      },
  { k:"perf",     l:"Performance" },
  { k:"ops",      l:"Ops" },
];

const WATCHLIST = ["AAPL","MSFT","NVDA","SPY","TSLA","AMZN","GOOGL","META"];
const CORE_PROFILES = [
  { key: "auto", label: "Auto" },
  { key: "balanced", label: "Balanced" },
  { key: "accuracy_max", label: "Accuracy Max" },
  { key: "latency_low", label: "Latency Low" },
  { key: "risk_off", label: "Risk Off" },
];

const REASON_LABELS = {
  confidence_below_threshold: "confidence",
  expected_utility_below_threshold: "utility",
  fundamentals_timestamp_missing: "fresh fundamentals",
  stale_market_data: "market data",
  low_confidence: "low confidence",
  policy_confidence_below_threshold: "policy confidence",
  policy_expected_utility_below_threshold: "policy utility",
  dominant_fundamental: "fundamental tilt",
};

const money = (value) =>
  Number(value || 0).toLocaleString("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  });

const percent = (value, digits = 2) => `${Number(value || 0).toFixed(digits)}%`;

const shortHash = (value) => {
  const text = String(value || "").trim();
  if (!text) return "n/a";
  if (text.length <= 16) return text;
  return `${text.slice(0, 8)}...${text.slice(-8)}`;
};

const humanizeReason = (value) => {
  const key = String(value || "").trim().toLowerCase();
  if (!key) return "";
  return REASON_LABELS[key] || key.replace(/_/g, " ");
};

export default function AlfredDashboard() {
  const [symbol,    setSymbol]    = useState("AAPL");
  const [input,     setInput]     = useState("AAPL");
  const [profile,   setProfile]   = useState("auto");
  const [signal,    setSignal]    = useState(null);
  const [positions, setPositions] = useState([]);
  const [news,      setNews]      = useState([]);
  const [risk,      setRisk]      = useState(null);
  const [tab,       setTab]       = useState("chart");
  
  // Use real-time data hooks
  const { ticks, wsStatus, cachedFetch, prefetchCache } = useRealTimeData();
  const { livePnL, livePnLBySymbol } = useLivePnL(positions);
  
  // Map WebSocket status to display label
  const ws = wsStatus === "connected" ? "live" : wsStatus === "connecting" ? "connecting" : "disconnected";

  const analyse = useCallback((sym) => {
    const s = (sym || input).trim().toUpperCase();
    if (!s) return;
    setSymbol(s); setInput(s);
    
    // Use cached fetches for signal and news
    cachedFetch(`signal-${s}-${profile}`, 
      () => getSignal(s, profile),
      30000 // 30-second cache for signals
    ).then(setSignal).catch(console.warn);
    
    cachedFetch(`news-${s}`,
      () => getNews(s),
      60000 // 60-second cache for news
    ).then(setNews).catch(console.warn);
  }, [input, profile, cachedFetch]);

  // Initial load - fetch positions and health once with caching
  useEffect(() => {
    prefetchCache('health', () => getHealth(), 10000);
    cachedFetch('positions',
      () => getPositions(),
      2000 // 2-second cache
    ).then(setPositions).catch(console.warn);
  }, [cachedFetch, prefetchCache]);

  // Fetch signal and news when symbol or profile changes
  useEffect(() => {
    cachedFetch(`signal-${symbol}-${profile}`, 
      () => getSignal(symbol, profile),
      30000
    ).then(setSignal).catch(console.warn);
    
    cachedFetch(`news-${symbol}`,
      () => getNews(symbol),
      60000
    ).then(setNews).catch(console.warn);
  }, [symbol, profile, cachedFetch]);

  const tick = ticks[symbol];
  const wsColor = ws==="live" ? "var(--green)" : ws==="connecting" ? "var(--amber)" : "var(--red)";
  const wsLabel = ws==="live" ? "LIVE" : ws==="connecting" ? "CONNECTING" : "OFFLINE";
  const openPositions = positions.filter((item) => Number(item.qty || 0) > 0);
  const totalMarketValue = openPositions.reduce((sum, item) => sum + Number(item.market_value || 0), 0);
  // Use live PnL from hook instead of manual calculation
  const totalUnrealized = livePnL;
  const diagnostics = signal?.diagnostics ?? {};
  const policy = diagnostics?.policy ?? {};
  const policyReasons = Array.from(new Set([
    ...(Array.isArray(policy?.rejections) ? policy.rejections : []),
    ...(Array.isArray(diagnostics?.reason_codes) ? diagnostics.reason_codes : []),
  ].filter(Boolean)));
  const policyChips = policyReasons.slice(0, 4).map(humanizeReason).filter(Boolean);
  const profileLabel = diagnostics?.profile || signal?.model?.profile || profile;
  const modelVersion = diagnostics?.model_versions?.meta_intent || signal?.model?.selected || "meta-intent-v1";
  const contractHash = shortHash(diagnostics?.determinism?.contract_hash);
  const coreBrief = policyChips.length
    ? `Contract is holding for ${policyChips.slice(0, 3).join(", ")}${policyChips.length > 3 ? ", and other guardrails" : ""}.`
    : "Deterministic contract is clear for the current symbol.";
  const leadHeadline = news[0]?.headline || "No current intelligence headline.";
  const leadPublishedAt = news[0]?.published_at ? new Date(news[0].published_at) : null;

  return (
    <div className="layout">

      {/* TOP BAR */}
      <header style={{
        gridArea:"topbar", background:"var(--bg1)", borderBottom:"1px solid var(--line)",
        display:"flex", alignItems:"center", padding:"0 14px", gap:12, zIndex:200,
      }}>
        {/* Logo */}
        <div style={{ display:"flex", alignItems:"center", gap:8, flexShrink:0 }}>
          <img src="/VektorLogo.png?v=20260422b" alt="Vektor Logo" style={{ height: "28px", width: "auto", objectFit: "contain" }} />
          <span style={{ fontFamily:"'Outfit'", fontWeight:700, fontSize:14, letterSpacing:"0.12em", color:"var(--amber)" }}>ALFRED</span>
        </div>

        <div style={{ width:1, height:20, background:"var(--line2)", flexShrink:0 }} />

        {/* Search */}
        <div style={{ display:"flex", gap:6, flexShrink:0 }}>
          <input className="inp" value={input}
            onChange={e=>setInput(e.target.value.toUpperCase())}
            onKeyDown={e=>e.key==="Enter"&&analyse()}
            placeholder="TICKER"
            style={{ width:84, padding:"5px 9px", fontSize:12 }} />
          <select
            className="inp"
            value={profile}
            onChange={(e) => setProfile(e.target.value)}
            style={{ width: 124, padding: "5px 8px", fontSize: 11 }}
          >
            {CORE_PROFILES.map((item) => (
              <option key={item.key} value={item.key}>{item.label}</option>
            ))}
          </select>
          <button className="btn btn-amber" onClick={()=>analyse()} style={{ padding:"5px 12px", fontSize:10 }}>
            Analyse
          </button>
        </div>

        {/* Ticker info - hidden on mobile */}
        {tick && (
          <div className="topbar-ticker" style={{ display:"flex", alignItems:"baseline", gap:8 }}>
            <span style={{ fontFamily:"var(--f-data)", fontSize:11, color:"var(--txt2)" }}>{symbol}</span>
            <span style={{ fontFamily:"var(--f-data)", fontSize:15, fontWeight:600 }}>${tick.price?.toFixed(2)}</span>
            <span style={{ fontFamily:"var(--f-data)", fontSize:11,
              color: tick.change>=0?"var(--green)":"var(--red)" }}>
              {tick.change>=0?"▲":"▼"} {Math.abs(tick.change||0).toFixed(2)}
              {" "}({tick.change_pct>=0?"+":""}{(tick.change_pct||0).toFixed(2)}%)
            </span>
          </div>
        )}

        {/* Tabs */}
        <div style={{ display:"flex", gap:2, marginLeft:8 }}>
          {TABS.map(({k,l}) => (
            <button key={k} className={`btn btn-tab ${tab===k?"on":""}`} onClick={()=>setTab(k)}>{l}</button>
          ))}
        </div>

        {/* Status */}
        <div style={{ marginLeft:"auto", display:"flex", alignItems:"center", gap:8 }}>
          <Clock />
          <div style={{ display:"flex", alignItems:"center", gap:5 }}>
            <div className="dot-live" style={{ background: wsColor }} />
            <span style={{ fontFamily:"var(--f-data)", fontSize:9, letterSpacing:"0.15em", color: wsColor }}>
              {wsLabel}
            </span>
          </div>
        </div>
      </header>

      {/* LEFT SIDEBAR */}
      <aside className="sidebar" style={{
        gridArea:"sidebar", background:"var(--bg1)", borderRight:"1px solid var(--line)",
        overflowY:"auto", display:"flex", flexDirection:"column", gap:0,
      }}>
        {/* Watchlist */}
        <div className="sec-head">
          <span className="label">Watchlist</span>
        </div>
        <div style={{ padding:"4px 0" }}>
          {WATCHLIST.map(sym => {
            const t = ticks[sym];
            const active = sym === symbol;
            const chg = t?.change ?? 0;
            return (
              <div key={sym} onClick={()=>analyse(sym)}
                style={{
                  display:"flex", alignItems:"center", justifyContent:"space-between",
                  padding:"7px 14px", cursor:"pointer", transition:"background 0.12s",
                  background: active ? "rgba(245,166,35,0.07)" : "transparent",
                  borderLeft: active ? "2px solid var(--amber)" : "2px solid transparent",
                }}
                onMouseEnter={e=>e.currentTarget.style.background=active?"rgba(245,166,35,0.07)":"rgba(255,255,255,0.03)"}
                onMouseLeave={e=>e.currentTarget.style.background=active?"rgba(245,166,35,0.07)":"transparent"}
              >
                <span style={{ fontFamily:"var(--f-data)", fontSize:12, fontWeight:600,
                  color: active?"var(--amber)":"var(--txt)" }}>{sym}</span>
                <div style={{ textAlign:"right" }}>
                  {t ? (
                    <>
                      <div style={{ fontFamily:"var(--f-data)", fontSize:11, color:"var(--txt)" }}>
                        ${t.price?.toFixed(2)}
                      </div>
                      <div style={{ fontFamily:"var(--f-data)", fontSize:9,
                        color: chg>=0?"var(--green)":"var(--red)" }}>
                        {chg>=0?"+":""}{chg.toFixed(2)}%
                      </div>
                    </>
                  ) : (
                    <span style={{ fontFamily:"var(--f-data)", fontSize:10, color:"var(--txt3)" }}>—</span>
                  )}
                </div>
              </div>
            );
          })}
        </div>

        <div className="divider" />

        {/* Positions in sidebar */}
        <div className="sec-head" style={{ marginTop:0 }}>
          <span className="label">Positions</span>
          {positions.filter(p=>p.qty>0).length > 0 && (
            <span style={{ fontFamily:"var(--f-data)", fontSize:10,
              color: positions.reduce((s,p)=>s+(p.unrealized_pnl??0),0) >= 0 ? "var(--green)" : "var(--red)" }}>
              {positions.reduce((s,p)=>s+(p.unrealized_pnl??0),0) >= 0 ? "+" : ""}
              ${positions.reduce((s,p)=>s+(p.unrealized_pnl??0),0).toFixed(2)}
            </span>
          )}
        </div>
        <Positions items={positions} compact />

        <div className="divider" />

        {/* Order in sidebar */}
        <div style={{ padding:"10px 14px" }}>
          <OrderPanel symbol={symbol}
            onPlace={async o => {
              const result = await placeOrder(o);
              if (result?.approved) {
                // Use cachedFetch to update positions (with 2-second cache)
                cachedFetch('positions',
                  () => getPositions(),
                  2000
                ).then(setPositions).catch(console.warn);
              }
              return result;
            }} />
        </div>
      </aside>

      {/* MAIN */}
      <main style={{
        gridArea:"main", overflowY:"auto", background:"var(--bg0)",
        display:"flex", flexDirection:"column", gap:10, padding:"10px 12px",
      }}>
        {/* Signal card always visible */}
        <div className="fade d1">
          <SignalCard signal={signal} symbol={symbol} tick={tick} />
        </div>

        {/* Tab content */}
        <div className="fade d2" style={{ flex:1, display:"flex", flexDirection:"column", gap:10 }}>
          {tab==="chart"    && (
            <>
              <TradingViewWidget symbol={symbol} height={460} />
              <div className="legacy-bottom-grid">
                <section className="panel panel-pad legacy-brief-card">
                  <div className="legacy-brief-head">
                    <span className="label">Core Brief</span>
                    <span className="legacy-brief-kicker">{String(profileLabel).toUpperCase()}</span>
                  </div>
                  <div className="legacy-brief-value">
                    {String(signal?.action || "hold").toUpperCase()} {Number(signal?.score || 0) >= 0 ? "+" : ""}{Number(signal?.score || 0).toFixed(3)}
                  </div>
                  <p className="legacy-brief-copy">{coreBrief}</p>
                  <div className="legacy-chip-row">
                    {policyChips.length ? policyChips.map((reason) => (
                      <span key={reason} className="legacy-chip">{reason}</span>
                    )) : <span className="legacy-chip">contract clear</span>}
                  </div>
                </section>

                <section className="panel panel-pad legacy-brief-card">
                  <div className="legacy-brief-head">
                    <span className="label">Execution Envelope</span>
                    <span className="legacy-brief-kicker">{policy?.safe_mode ? "SAFE HOLD" : "CLEAR"}</span>
                  </div>
                  <div className="legacy-stat-grid">
                    <div className="legacy-stat">
                      <span>Confidence</span>
                      <strong>{percent(Number(signal?.confidence || 0) * 100, 1)}</strong>
                    </div>
                    <div className="legacy-stat">
                      <span>ATR</span>
                      <strong>{percent(Number(signal?.volatility || diagnostics?.technical?.atr_pct || 0) * 100, 2)}</strong>
                    </div>
                    <div className="legacy-stat">
                      <span>Model</span>
                      <strong>{modelVersion}</strong>
                    </div>
                    <div className="legacy-stat">
                      <span>Contract</span>
                      <strong>{contractHash}</strong>
                    </div>
                  </div>
                </section>

                <section className="panel panel-pad legacy-brief-card">
                  <div className="legacy-brief-head">
                    <span className="label">Book And Wire</span>
                    <span className="legacy-brief-kicker">{wsLabel}</span>
                  </div>
                  <div className="legacy-stat-grid">
                    <div className="legacy-stat">
                      <span>Positions</span>
                      <strong>{openPositions.length}</strong>
                    </div>
                    <div className="legacy-stat">
                      <span>Exposure</span>
                      <strong>{money(totalMarketValue)}</strong>
                    </div>
                    <div className="legacy-stat">
                      <span>uPnL</span>
                      <strong style={{ color: totalUnrealized >= 0 ? "var(--green)" : "var(--red)" }}>{money(totalUnrealized)}</strong>
                    </div>
                    <div className="legacy-stat">
                      <span>Lead wire</span>
                      <strong>{leadPublishedAt ? leadPublishedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : "n/a"}</strong>
                    </div>
                  </div>
                  <p className="legacy-brief-copy">{leadHeadline}</p>
                </section>
              </div>
            </>
          )}
          {tab==="backtest" && <BacktestPanel />}
          {tab==="risk"     && <RiskDashboard riskData={risk} />}
          {tab==="perf"     && <StrategyDashboard />}
          {tab==="ops"      && <OpsPanel />}
        </div>
      </main>

      {/* NEWS */}
      <aside className="news-col" style={{
        gridArea:"news", background:"var(--bg1)", borderLeft:"1px solid var(--line)",
        overflowY:"auto", display:"flex", flexDirection:"column",
      }}>
        <NewsFeed symbol={symbol} items={news} />
      </aside>
    </div>
  );
}

function Clock() {
  const [t, setT] = useState(new Date());
  useEffect(() => { const id=setInterval(()=>setT(new Date()),1000); return()=>clearInterval(id); }, []);
  return (
    <span style={{ fontFamily:"var(--f-data)", fontSize:10, color:"var(--txt3)", letterSpacing:"0.08em" }}>
      {t.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit",second:"2-digit"})}
    </span>
  );
}


