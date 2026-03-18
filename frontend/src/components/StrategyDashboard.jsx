import React, { useEffect, useState } from "react"
import { getAnalytics } from "../api"

export default function StrategyDashboard() {
  const [data,setData]=useState(null)
  useEffect(()=>{ const l=async()=>{ try{setData(await getAnalytics())}catch{} }; l(); const id=setInterval(l,10000); return()=>clearInterval(id) },[])

  if (!data) return <div style={{padding:20,color:"var(--txt3)",fontFamily:"var(--f-data)",fontSize:10}}>LOADING…</div>

  const {total_trades=0,closed_trades=0,wins=0,losses=0,win_rate=0,
    realized_pnl=0,avg_pnl=0,best_trade=0,worst_trade=0,max_drawdown=0,recent_trades=[]}=data

  const stats=[
    {l:"Trades",   v:total_trades},
    {l:"Closed",   v:closed_trades},
    {l:"Wins",     v:wins,    c:"var(--green)"},
    {l:"Losses",   v:losses,  c:"var(--red)"},
    {l:"Win Rate", v:`${win_rate.toFixed(1)}%`},
    {l:"Realized", v:`$${realized_pnl.toFixed(2)}`, c:realized_pnl>=0?"var(--green)":"var(--red)"},
    {l:"Avg PnL",  v:`$${avg_pnl.toFixed(2)}`,      c:avg_pnl>=0?"var(--green)":"var(--red)"},
    {l:"Max DD",   v:`$${max_drawdown.toFixed(2)}`,  c:"var(--red)"},
    {l:"Best",     v:`$${best_trade.toFixed(2)}`,    c:"var(--green)"},
    {l:"Worst",    v:`$${worst_trade.toFixed(2)}`,   c:"var(--red)"},
  ]

  return (
    <div style={{display:"flex",flexDirection:"column",gap:10}}>
      <div className="panel panel-pad">
        <div className="label" style={{marginBottom:12}}>Performance Summary</div>
        <div style={{display:"grid",gridTemplateColumns:"repeat(5,1fr)",gap:8}} className="stat-grid-8">
          {stats.map(({l,v,c})=>(
            <div key={l} style={{background:"var(--bg3)",border:"1px solid var(--line)",borderRadius:"var(--r-sm)",padding:"9px 11px"}}>
              <div className="label" style={{marginBottom:4,fontSize:8}}>{l}</div>
              <div style={{fontFamily:"var(--f-data)",fontSize:14,fontWeight:600,color:c||"var(--txt)"}}>{v}</div>
            </div>
          ))}
        </div>
      </div>
      <div className="panel panel-pad">
        <div className="label" style={{marginBottom:10}}>Recent Round Trips</div>
        <table className="tbl">
          <thead><tr>
            <th style={{textAlign:"left"}}>TIME</th><th style={{textAlign:"left"}}>SYM</th>
            <th>QTY</th><th>BUY</th><th>SELL</th><th>PNL</th>
          </tr></thead>
          <tbody>
            {!recent_trades.length ? (
              <tr><td colSpan={6} style={{padding:"20px 0",textAlign:"center",color:"var(--txt3)"}}>No closed trades</td></tr>
            ) : recent_trades.map((t,i)=>(
              <tr key={i}>
                <td style={{color:"var(--txt3)"}}>{new Date(t.close_ts).toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"})}</td>
                <td style={{fontWeight:600}}>{t.symbol}</td>
                <td>{t.qty}</td>
                <td>${t.buy.toFixed(2)}</td>
                <td>${t.sell.toFixed(2)}</td>
                <td style={{color:t.pnl>=0?"var(--green)":"var(--red)",fontWeight:600}}>
                  {t.pnl>=0?"+":""}${t.pnl.toFixed(2)}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}