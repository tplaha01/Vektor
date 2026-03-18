import React, { useEffect, useState } from "react"
import { getNews } from "../api"
import { SentimentIntensityAnalyzer } from "vader-sentiment"

export default function NewsFeed({ symbol }) {
  const [items, setItems] = useState([])
  const [avg,   setAvg]   = useState(0)

  useEffect(() => {
    const load = async () => { try { setItems(await getNews(symbol)||[]) } catch {} }
    load(); const id=setInterval(load,60000); return ()=>clearInterval(id)
  }, [symbol])

  useEffect(() => {
    if (!items.length) return
    const s = items.map(n=>SentimentIntensityAnalyzer.polarity_scores(n.headline||"").compound)
    setAvg(s.reduce((a,b)=>a+b,0)/s.length)
  }, [items])

  const col = avg>0.2?"var(--green)":avg<-0.2?"var(--red)":"var(--amber)"
  const lbl = avg>0.2?"BULLISH":avg<-0.2?"BEARISH":"NEUTRAL"

  return (
    <>
      <div className="sec-head">
        <span className="label">Intelligence · {symbol}</span>
        <div style={{ display:"flex", alignItems:"center", gap:6 }}>
          <div style={{ width:32, height:2, borderRadius:1, background:"var(--line)", overflow:"hidden" }}>
            <div style={{ height:"100%", width:`${Math.min(100,Math.abs(avg)*100)}%`, background:col, transition:"width 0.6s" }} />
          </div>
          <span style={{ fontFamily:"var(--f-data)", fontSize:9, letterSpacing:"0.1em", color:col }}>{lbl}</span>
        </div>
      </div>

      <div style={{ overflowY:"auto", flex:1 }}>
        {items.length===0 && (
          <div style={{ padding:"32px 14px", textAlign:"center", color:"var(--txt3)",
            fontFamily:"var(--f-data)", fontSize:10, letterSpacing:"0.1em" }}>
            NO HEADLINES
          </div>
        )}
        {items.map((n,i) => {
          const sc  = SentimentIntensityAnalyzer.polarity_scores(n.headline||"").compound
          const col = sc>0.2?"var(--green)":sc<-0.2?"var(--red)":"var(--amber)"
          const lbl = sc>0.2?"BULL":sc<-0.2?"BEAR":"NEUT"
          const ts  = n.ts ? new Date(n.ts*1000) : null
          return (
            <div key={i} style={{
              padding:"10px 14px", borderBottom:"1px solid var(--line)",
              cursor:"pointer", transition:"background 0.12s",
            }}
            onMouseEnter={e=>e.currentTarget.style.background="rgba(255,255,255,0.02)"}
            onMouseLeave={e=>e.currentTarget.style.background="transparent"}>
              <div style={{ display:"flex", justifyContent:"space-between", marginBottom:4 }}>
                <span style={{ fontFamily:"var(--f-data)", fontSize:8, color:"var(--txt3)", letterSpacing:"0.1em" }}>
                  {ts?ts.toLocaleTimeString([],{hour:"2-digit",minute:"2-digit"}):"—"}
                </span>
                <span className="pill" style={{ borderColor:col, color:col, fontSize:7 }}>{lbl}</span>
              </div>
              <div style={{ fontFamily:"var(--f-ui)", fontSize:11, lineHeight:1.55, color:"var(--txt)" }}>
                {n.headline}
              </div>
            </div>
          )
        })}
      </div>
    </>
  )
}