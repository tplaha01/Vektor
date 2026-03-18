import React, { useState } from "react"

export default function OrderPanel({ symbol, onPlace }) {
  const [side, setSide] = useState("buy")
  const [qty,  setQty]  = useState("1")
  const [busy, setBusy] = useState(false)
  const [msg,  setMsg]  = useState(null)

  const submit = async () => {
    setBusy(true); setMsg(null)
    try {
      await onPlace({ symbol, side, quantity: parseFloat(qty)||1 })
      setMsg({ ok:true, text:"Order submitted" })
    } catch(e) { setMsg({ ok:false, text:e.message }) }
    finally { setBusy(false); setTimeout(()=>setMsg(null), 3000) }
  }

  return (
    <div style={{ display:"flex", flexDirection:"column", gap:8 }}>
      <span className="label">Quick Order</span>
      <div style={{ display:"flex", gap:4 }}>
        {["buy","sell"].map(s => (
          <button key={s} className="btn-side" onClick={()=>setSide(s)} style={{
            background: side===s ? (s==="buy"?"var(--green)":"var(--red)") : "var(--bg3)",
            color: side===s ? (s==="buy"?"#001a0d":"#150000") : "var(--txt3)",
            border: side===s ? "none" : "1px solid var(--line)",
          }}>{s.toUpperCase()}</button>
        ))}
      </div>
      <div style={{ display:"flex", gap:6 }}>
        <div style={{ flex:1, background:"var(--bg3)", border:"1px solid var(--line)", borderRadius:"var(--r-sm)",
          padding:"6px 8px", fontFamily:"var(--f-data)", fontSize:11, color:"var(--txt2)", letterSpacing:"0.06em" }}>
          {symbol}
        </div>
        <input type="number" min="1" value={qty} onChange={e=>setQty(e.target.value)}
          className="inp" style={{ width:60, textAlign:"center", textTransform:"none" }} />
      </div>
      <button className="btn btn-amber" onClick={submit} disabled={busy} style={{ width:"100%" }}>
        {busy ? "…" : `${side==="buy"?"Buy":"Sell"} ${qty}`}
      </button>
      {msg && (
        <div style={{ fontFamily:"var(--f-data)", fontSize:9, textAlign:"center", letterSpacing:"0.1em",
          color: msg.ok?"var(--green)":"var(--red)" }}>{msg.text}</div>
      )}
    </div>
  )
}