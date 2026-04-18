import React, { useEffect, useState } from "react"
const BASE = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000"

function Cell({ label, value, color }) {
  return (
    <div style={{ background:"var(--bg3)", border:"1px solid var(--line)", borderRadius:"var(--r-sm)", padding:"10px 12px" }}>
      <div className="label" style={{ marginBottom:5 }}>{label}</div>
      <div style={{ fontFamily:"var(--f-data)", fontSize:16, fontWeight:600, color:color||"var(--txt)" }}>{value}</div>
    </div>
  )
}

export default function RiskDashboard({ riskData:ext }) {
  const [data,setData]=useState(ext||null)
  const [error, setError] = useState(null)
  const [loading, setLoading] = useState(!ext)
  
  useEffect(()=>{ 
    const l = async () => {
      try {
        const r = await fetch(`${BASE}/risk/status`)
        if (!r.ok) throw new Error(`Risk endpoint returned ${r.status}`)
        const d = await r.json()
        setData(d)
        setError(null)
      } catch (err) {
        console.error('Risk dashboard error:', err)
        setError(err.message || 'Failed to load risk data')
      } finally {
        setLoading(false)
      }
    }
    l()
    const id = setInterval(l, 5000)
    return () => clearInterval(id)
  }, [])
  
  useEffect(()=>{ if(ext){setData(ext); setLoading(false)} },[ext])

  if (error) return <div style={{ padding:20, color:"var(--red)", fontFamily:"var(--f-data)", fontSize:11 }}>⚠ {error}</div>
  if (loading) return <div style={{ padding:20, color:"var(--txt3)", fontFamily:"var(--f-data)", fontSize:10 }}>LOADING…</div>
  if (!data) return <div style={{ padding:20, color:"var(--txt3)", fontFamily:"var(--f-data)", fontSize:10 }}>NO DATA</div>

  const dd=data.drawdown_breaker??{}, stops=data.open_stops??[]
  const equity=data.equity??100000, peak=dd.peak_equity??equity
  const ddPct=peak>0?((equity-peak)/peak*100):0

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:10 }}>
      <div className="panel panel-pad">
        <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:12 }}>
          <span className="label">Risk Engine</span>
          <div style={{ display:"flex", alignItems:"center", gap:6 }}>
            <div className="dot-live" style={{ background: dd.halted?"var(--red)":"var(--green)" }} />
            <span style={{ fontFamily:"var(--f-data)", fontSize:9, letterSpacing:"0.15em",
              color: dd.halted?"var(--red)":"var(--green)" }}>
              {dd.halted?"HALTED":"ACTIVE"}
            </span>
          </div>
        </div>
        <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:8 }} className="stat-grid-4">
          <Cell label="Portfolio" value={`$${equity.toLocaleString("en-US",{maximumFractionDigits:0})}`} />
          <Cell label="Peak"      value={`$${peak.toLocaleString("en-US",{maximumFractionDigits:0})}`} />
          <Cell label="Drawdown"  value={`${ddPct.toFixed(2)}%`}
            color={ddPct<-5?"var(--red)":ddPct<-2?"var(--amber)":"var(--green)"} />
          <Cell label="DD Limit"  value={`${((dd.max_drawdown_threshold??0.1)*100).toFixed(0)}%`} color="var(--txt2)" />
        </div>
      </div>

      <div className="panel panel-pad">
        <div className="label" style={{ marginBottom:10 }}>ATR Stop Levels</div>
        {stops.length===0 ? (
          <div style={{ fontFamily:"var(--f-data)", fontSize:10, color:"var(--txt3)", padding:"8px 0" }}>No open stops</div>
        ) : (
          <table className="tbl">
            <thead><tr>
              <th style={{textAlign:"left"}}>SYM</th><th>ENTRY</th><th>STOP</th><th>TP</th><th>ATR</th>
            </tr></thead>
            <tbody>
              {stops.map((s,i)=>(
                <tr key={i}>
                  <td style={{fontWeight:600}}>{s.symbol}</td>
                  <td>${s.entry_price.toFixed(2)}</td>
                  <td className="c-red">${s.stop_price.toFixed(2)}</td>
                  <td className="c-green">${s.tp_price.toFixed(2)}</td>
                  <td className="c-dim">{s.atr_at_entry.toFixed(2)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}