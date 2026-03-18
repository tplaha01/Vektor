import React, { useState } from "react"
import { AreaChart, Area, BarChart, Bar, XAxis, YAxis, CartesianGrid,
  Tooltip, ResponsiveContainer, ReferenceLine, Legend } from "recharts"

const BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"
const REGIME_C = { TREND_UP:"var(--green)",TREND_DOWN:"var(--red)",BREAKOUT_UP:"var(--teal)",
  BREAKOUT_DOWN:"#fb923c",RANGE:"var(--amber)",HIGH_VOL:"var(--purple)" }
const fmt    = (n,d=2) => n==null?"—":Number(n).toFixed(d)
const fmtPct = n => `${n>=0?"+":""}${fmt(n)}%`
const fmtUSD = n => `$${Number(n).toLocaleString("en-US",{maximumFractionDigits:0})}`
const clr    = n => n>0?"var(--green)":n<0?"var(--red)":"var(--txt2)"
const TT = { background:"var(--bg3)",border:"1px solid var(--line2)",borderRadius:4,
  fontFamily:"var(--f-data)",fontSize:10,color:"var(--txt)",padding:"7px 10px" }
const GR = { stroke:"rgba(255,255,255,0.04)",strokeDasharray:"3 3" }
const TX = { fill:"var(--txt3)",fontSize:9,fontFamily:"var(--f-data)" }

function Cell({label,value,color}) {
  return (
    <div style={{background:"var(--bg3)",border:"1px solid var(--line)",borderRadius:"var(--r-sm)",padding:"9px 11px"}}>
      <div className="label" style={{marginBottom:4,fontSize:8}}>{label}</div>
      <div style={{fontFamily:"var(--f-data)",fontSize:14,fontWeight:600,color:color||"var(--txt)"}}>{value}</div>
    </div>
  )
}

export default function BacktestPanel() {
  const [symbol,  setSym]  = useState("AAPL")
  const [period,  setPer]  = useState("1y")
  const [buyThr,  setBuy]  = useState(0.12)
  const [sellThr, setSell] = useState(0.12)
  const [loading, setLoad] = useState(false)
  const [error,   setErr]  = useState(null)
  const [result,  setRes]  = useState(null)
  const [tab,     setTab]  = useState("equity")

  const run = async () => {
    setLoad(true); setErr(null)
    try {
      const r = await fetch(`${BASE}/backtest/run`, {
        method:"POST", headers:{"Content-Type":"application/json"},
        body: JSON.stringify({ symbol:symbol.toUpperCase(), period, buy_threshold:buyThr, sell_threshold:-sellThr }),
      })
      if (!r.ok) throw new Error((await r.json()).detail||"Failed")
      setRes(await r.json()); setTab("equity")
    } catch(e) { setErr(e.message) }
    finally { setLoad(false) }
  }

  const m = result?.metrics??{}

  const merged = (() => {
    if (!result) return []
    const bMap={}; result.benchmark_curve?.forEach(p=>{bMap[p.date]=p.equity})
    return result.equity_curve.map(p=>({date:p.date.slice(5),strategy:p.equity,benchmark:bMap[p.date]??null}))
  })()

  const ddData = (() => {
    let peak=0
    return merged.map(p=>{ if(p.strategy>peak)peak=p.strategy; return{date:p.date,dd:peak>0?+((p.strategy-peak)/peak*100).toFixed(2):0} })
  })()

  return (
    <div style={{display:"flex",flexDirection:"column",gap:10}}>
      {/* Controls */}
      <div className="panel panel-pad">
        <div style={{display:"flex",flexWrap:"wrap",alignItems:"center",gap:8,marginBottom:10}}>
          <span className="label">Backtester</span>
          <input className="inp" value={symbol} onChange={e=>setSym(e.target.value.toUpperCase())}
            onKeyDown={e=>e.key==="Enter"&&run()} style={{width:76,padding:"5px 8px"}} />
          {["6mo","1y","2y","3y"].map(p=>(
            <button key={p} className={`btn btn-tab ${period===p?"on":""}`} onClick={()=>setPer(p)}>{p}</button>
          ))}
          <button className="btn btn-amber" onClick={run} disabled={loading} style={{marginLeft:"auto"}}>
            {loading?"Running…":"Run Backtest"}
          </button>
        </div>
        <div className="divider" style={{marginBottom:8}} />
        <div style={{display:"flex",flexWrap:"wrap",gap:4,alignItems:"center"}}>
          <span style={{fontFamily:"var(--f-data)",fontSize:9,color:"var(--txt3)",letterSpacing:"0.12em",marginRight:4}}>ENTRY ≥</span>
          {[0.08,0.10,0.12,0.15,0.20].map(v=>(
            <button key={v} className={`btn btn-tab ${buyThr===v?"on":""}`} onClick={()=>setBuy(v)}
              style={{padding:"3px 8px",fontSize:9}}>{v}</button>
          ))}
          <span style={{fontFamily:"var(--f-data)",fontSize:9,color:"var(--txt3)",letterSpacing:"0.12em",margin:"0 4px 0 10px"}}>EXIT ≤</span>
          {[0.08,0.10,0.12,0.15,0.20].map(v=>(
            <button key={v} onClick={()=>setSell(v)}
              className="btn btn-tab" style={{padding:"3px 8px",fontSize:9,
                ...(sellThr===v?{color:"var(--red)",borderColor:"rgba(224,82,82,0.3)",background:"rgba(224,82,82,0.06)"}:{})}}>
              -{v}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div style={{padding:"9px 12px",borderRadius:"var(--r-sm)",background:"rgba(224,82,82,0.1)",
          border:"1px solid rgba(224,82,82,0.25)",fontFamily:"var(--f-data)",fontSize:10,color:"var(--red)"}}>
          {error}
        </div>
      )}

      {loading && (
        <div style={{textAlign:"center",padding:"40px 0",fontFamily:"var(--f-data)",fontSize:10,color:"var(--txt3)",letterSpacing:"0.15em"}}>
          COMPUTING REGIME SIGNALS…
        </div>
      )}

      {result && !loading && (
        <>
          <div style={{display:"grid",gridTemplateColumns:"repeat(8,1fr)",gap:7}} className="stat-grid-8">
            <Cell label="Return"        value={fmtPct(m.total_return_pct)}   color={clr(m.total_return_pct)} />
            <Cell label="vs SPY"        value={fmtPct(m.alpha_pct)}          color={clr(m.alpha_pct)} />
            <Cell label="CAGR"          value={fmtPct(m.cagr_pct)}           color={clr(m.cagr_pct)} />
            <Cell label="Sharpe"        value={fmt(m.sharpe,3)}              color={clr(m.sharpe)} />
            <Cell label="Sortino"       value={fmt(m.sortino,3)}             color={clr(m.sortino)} />
            <Cell label="Max DD"        value={fmtPct(m.max_drawdown_pct)}   color="var(--red)" />
            <Cell label="Win Rate"      value={`${fmt(m.win_rate_pct,1)}%`}  color={clr(m.win_rate_pct-50)} />
            <Cell label="Prof. Factor"  value={fmt(m.profit_factor,2)}       color={clr(m.profit_factor-1)} />
          </div>
          <div style={{display:"grid",gridTemplateColumns:"repeat(4,1fr)",gap:7}} className="stat-grid-4">
            <Cell label="Calmar"  value={fmt(m.calmar,3)}        color={clr(m.calmar)} />
            <Cell label="Trades"  value={m.total_trades} />
            <Cell label="Avg Hold" value={`${fmt(m.avg_hold_days,1)}d`} />
            <Cell label="Final"   value={fmtUSD(m.final_equity)} color={clr(m.final_equity-100000)} />
          </div>

          {m.regime_breakdown && Object.keys(m.regime_breakdown).length>0 && (
            <div style={{display:"flex",flexWrap:"wrap",gap:5,alignItems:"center"}}>
              <span className="label" style={{marginRight:4}}>Regimes</span>
              {Object.entries(m.regime_breakdown).map(([r,n])=>(
                <span key={r} className="pill" style={{color:REGIME_C[r]??"var(--txt2)",
                  borderColor:`${REGIME_C[r]??"var(--line)"}44`,
                  background:`${REGIME_C[r]??"transparent"}0d`,fontSize:8,letterSpacing:"0.1em"}}>
                  {r.replace("_"," ")}: {n}
                </span>
              ))}
            </div>
          )}

          <div className="panel panel-pad">
            <div style={{display:"flex",gap:4,marginBottom:12}}>
              {[["equity","Equity"],["drawdown","Drawdown"],["trades","Trades"],["signal","Signal"]].map(([k,l])=>(
                <button key={k} className={`btn btn-tab ${tab===k?"on":""}`} onClick={()=>setTab(k)}>{l}</button>
              ))}
            </div>

            {tab==="equity" && (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={merged} margin={{top:4,right:4,bottom:0,left:8}}>
                  <defs>
                    <linearGradient id="gA" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="10%" stopColor="var(--amber)" stopOpacity={0.3}/>
                      <stop offset="95%" stopColor="var(--amber)" stopOpacity={0}/>
                    </linearGradient>
                    <linearGradient id="gS" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="10%" stopColor="var(--txt3)" stopOpacity={0.15}/>
                      <stop offset="95%" stopColor="var(--txt3)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...GR}/><XAxis dataKey="date" tick={TX} tickLine={false} interval="preserveStartEnd"/>
                  <YAxis tickFormatter={v=>`$${(v/1000).toFixed(0)}k`} tick={TX} tickLine={false} axisLine={false}/>
                  <Tooltip contentStyle={TT}/>
                  <Legend wrapperStyle={{fontFamily:"var(--f-data)",fontSize:9,color:"var(--txt3)"}}/>
                  <Area type="monotone" dataKey="benchmark" name="SPY"    stroke="var(--txt3)" strokeWidth={1} fill="url(#gS)" dot={false} strokeDasharray="3 3" opacity={0.5}/>
                  <Area type="monotone" dataKey="strategy"  name="Alfred" stroke="var(--amber)" strokeWidth={2} fill="url(#gA)" dot={false}/>
                </AreaChart>
              </ResponsiveContainer>
            )}
            {tab==="drawdown" && (
              <ResponsiveContainer width="100%" height={200}>
                <AreaChart data={ddData} margin={{top:4,right:4,bottom:0,left:8}}>
                  <defs>
                    <linearGradient id="gD" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor="var(--red)" stopOpacity={0.4}/>
                      <stop offset="95%" stopColor="var(--red)" stopOpacity={0}/>
                    </linearGradient>
                  </defs>
                  <CartesianGrid {...GR}/><XAxis dataKey="date" tick={TX} tickLine={false} interval="preserveStartEnd"/>
                  <YAxis tickFormatter={v=>`${v.toFixed(1)}%`} tick={TX} tickLine={false} axisLine={false}/>
                  <Tooltip formatter={v=>[`${v}%`,"DD"]} contentStyle={TT}/>
                  <ReferenceLine y={0} stroke="rgba(255,255,255,0.06)"/>
                  <Area type="monotone" dataKey="dd" stroke="var(--red)" strokeWidth={1.5} fill="url(#gD)" dot={false}/>
                </AreaChart>
              </ResponsiveContainer>
            )}
            {tab==="trades" && (
              <div style={{overflowY:"auto",maxHeight:200}}>
                {!result.trades.length ? (
                  <div style={{textAlign:"center",padding:"24px 0",color:"var(--txt3)",fontFamily:"var(--f-data)",fontSize:10}}>
                    NO TRADES
                  </div>
                ) : (
                  <table className="tbl">
                    <thead><tr>
                      <th style={{textAlign:"left"}}>REGIME</th><th style={{textAlign:"left"}}>ENTRY</th>
                      <th style={{textAlign:"left"}}>EXIT</th><th>DAYS</th><th>ENTRY$</th><th>EXIT$</th><th>PNL</th><th>REASON</th>
                    </tr></thead>
                    <tbody>
                      {[...result.trades].reverse().map((t,i)=>(
                        <tr key={i}>
                          <td><span className="pill" style={{color:REGIME_C[t.regime]??"var(--txt2)",
                            borderColor:`${REGIME_C[t.regime]??"var(--line)"}44`,
                            background:`${REGIME_C[t.regime]??"transparent"}0d`,fontSize:7}}>
                            {t.regime?.replace("_"," ")??"—"}
                          </span></td>
                          <td style={{color:"var(--txt2)"}}>{t.entry_date}</td>
                          <td style={{color:"var(--txt2)"}}>{t.exit_date}</td>
                          <td>{t.hold_days}</td>
                          <td>${t.entry_price?.toFixed(2)}</td>
                          <td>${t.exit_price?.toFixed(2)}</td>
                          <td style={{fontWeight:600,color:t.pnl>=0?"var(--green)":"var(--red)"}}>
                            {t.pnl>=0?"+":""}{t.pnl?.toFixed(2)}
                          </td>
                          <td><span className="pill" style={{fontSize:7,
                            color:t.exit_reason==="tp"?"var(--green)":t.exit_reason==="stop"?"var(--red)":"var(--teal)",
                            borderColor:`${t.exit_reason==="tp"?"var(--green)":t.exit_reason==="stop"?"var(--red)":"var(--teal)"}44`}}>
                            {t.exit_reason}
                          </span></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            )}
            {tab==="signal" && (
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={result.signal_series?.map(p=>({date:p.date?.slice(5),signal:p.signal}))} margin={{top:4,right:4,bottom:0,left:8}}>
                  <CartesianGrid {...GR}/><XAxis dataKey="date" tick={TX} tickLine={false} interval="preserveStartEnd"/>
                  <YAxis domain={[-1,1]} tickFormatter={v=>v.toFixed(1)} tick={TX} tickLine={false} axisLine={false}/>
                  <Tooltip formatter={v=>[v?.toFixed(4),"Signal"]} contentStyle={TT}/>
                  <ReferenceLine y={buyThr}   stroke="var(--green)" strokeDasharray="3 3" opacity={0.6}/>
                  <ReferenceLine y={-sellThr} stroke="var(--red)"   strokeDasharray="3 3" opacity={0.6}/>
                  <ReferenceLine y={0} stroke="rgba(255,255,255,0.06)"/>
                  <Bar dataKey="signal" fill="var(--amber)" opacity={0.8} radius={[1,1,0,0]}/>
                </BarChart>
              </ResponsiveContainer>
            )}

            {m.exit_reasons && (
              <div style={{display:"flex",gap:5,marginTop:10,flexWrap:"wrap",alignItems:"center",
                borderTop:"1px solid var(--line)",paddingTop:8}}>
                <span className="label" style={{marginRight:4}}>Exits</span>
                {Object.entries(m.exit_reasons).map(([k,v])=>(
                  <span key={k} className="pill" style={{fontSize:8,
                    color:k==="tp"?"var(--green)":k==="stop"?"var(--red)":"var(--teal)",
                    borderColor:`${k==="tp"?"var(--green)":k==="stop"?"var(--red)":"var(--teal)"}44`}}>
                    {k}: {v}
                  </span>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {!result&&!loading&&!error && (
        <div style={{textAlign:"center",padding:"56px 0"}}>
          <div style={{fontFamily:"var(--f-data)",fontSize:11,color:"var(--txt3)",letterSpacing:"0.2em",marginBottom:8}}>
            ENTER TICKER · SELECT PERIOD · RUN
          </div>
          <div style={{fontFamily:"var(--f-ui)",fontSize:11,color:"var(--txt3)",opacity:0.6}}>
            Regime-adaptive · Trend · Mean Reversion · Breakout · Defensive
          </div>
        </div>
      )}
    </div>
  )
}