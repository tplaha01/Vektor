import React from "react"

export default function Positions({ items=[], compact=false }) {
  const open = items.filter(p => p.qty > 0)

  if (open.length === 0) return (
    <div style={{ padding:"14px", textAlign:"center", color:"var(--txt3)",
      fontFamily:"var(--f-data)", fontSize:10, letterSpacing:"0.1em" }}>
      NO OPEN POSITIONS
    </div>
  )

  return (
    <div style={{ padding: compact ? "6px 14px" : "12px 14px" }}>
      <table className="tbl">
        <thead>
          <tr>
            <th style={{ textAlign:"left" }}>SYM</th>
            <th>QTY</th>
            <th>LAST</th>
            <th>uPnL</th>
          </tr>
        </thead>
        <tbody>
          {open.map((p,i) => {
            const pct = p.avg_price>0 ? ((p.market_price-p.avg_price)/p.avg_price*100) : 0
            return (
              <tr key={i}>
                <td style={{ fontWeight:600, letterSpacing:"0.06em" }}>{p.symbol}</td>
                <td className="c-mute">{p.qty}</td>
                <td>${p.market_price?.toFixed(2)}</td>
                <td style={{ color: p.unrealized_pnl>=0?"var(--green)":"var(--red)", fontWeight:500 }}>
                  <div>{p.unrealized_pnl>=0?"+":""}{(p.unrealized_pnl??0).toFixed(2)}</div>
                  <div style={{ fontSize:9, opacity:0.7 }}>{pct>=0?"+":""}{pct.toFixed(2)}%</div>
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}