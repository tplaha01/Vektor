import React, { useEffect, useState, useRef } from "react";
import { getSignal, getPositions, placeOrder, wsConnect, getNews, getHealth } from "../api";
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
  { key: "balanced", label: "Balanced" },
  { key: "accuracy_max", label: "Accuracy Max" },
  { key: "latency_low", label: "Latency Low" },
  { key: "risk_off", label: "Risk Off" },
];

export default function AlfredDashboard() {
  const [symbol,    setSymbol]    = useState("AAPL");
  const [input,     setInput]     = useState("AAPL");
  const [profile,   setProfile]   = useState("balanced");
  const [signal,    setSignal]    = useState(null);
  const [positions, setPositions] = useState([]);
  const [ticks,     setTicks]     = useState({});
  const [news,      setNews]      = useState([]);
  const [ws,        setWs]        = useState("connecting");
  const [risk,      setRisk]      = useState(null);
  const [tab,       setTab]       = useState("chart");
  const wsRef = useRef(null);

  const analyse = (sym) => {
    const s = (sym || input).trim().toUpperCase();
    if (!s) return;
    setSymbol(s); setInput(s);
    getSignal(s, profile).then(setSignal).catch(console.warn);
    getNews(s).then(setNews).catch(console.warn);
  };

  useEffect(() => {
    getHealth().catch(console.warn);
    getPositions().then(setPositions).catch(console.warn);
  }, []);

  useEffect(() => {
    getSignal(symbol, profile).then(setSignal).catch(console.warn);
    getNews(symbol).then(setNews).catch(console.warn);
  }, [symbol, profile]);

  useEffect(() => {
    let dead = false;
    function connect() {
      if (dead) return;
      setWs("connecting");
      const sock = wsConnect(msg => {
        if (msg.type === "tick_batch") {
          setTicks(p => { const m={...p}; msg.data.forEach(d=>m[d.symbol]=d); return m; });
          setWs("live");
        }
        if (msg.type === "positions_update") setPositions(msg.data);
        if (msg.type === "risk_update")      setRisk(msg.data);
      });
      sock.onopen  = () => setWs("live");
      sock.onclose = () => { setWs("disconnected"); if (!dead) setTimeout(connect, 3000); };
      sock.onerror = () => setWs("disconnected");
      wsRef.current = sock;
    }
    connect();
    const poll = setInterval(() => getPositions().then(setPositions).catch(console.warn), 10000);
    return () => { dead=true; clearInterval(poll); wsRef.current?.close(); };
  }, []);

  const tick = ticks[symbol];
  const wsColor = ws==="live" ? "var(--green)" : ws==="connecting" ? "var(--amber)" : "var(--red)";
  const wsLabel = ws==="live" ? "LIVE" : ws==="connecting" ? "CONNECTING" : "OFFLINE";

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
            onPlace={async o => { await placeOrder(o); getPositions().then(setPositions); }} />
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
          {tab==="chart"    && <TradingViewWidget symbol={symbol} />}
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


