import React, { useEffect, useRef } from "react"

export default function TradingViewWidget({ symbol, height = 280 }) {
  const ref  = useRef()
  const uid  = useRef(`tv_${Math.random().toString(36).slice(2,9)}`)

  useEffect(() => {
    if (!ref.current) return
    ref.current.innerHTML = ""

    const container = document.createElement("div")
    container.id = uid.current
    container.style.cssText = "width:100%;height:100%;"
    ref.current.appendChild(container)

    const init = () => {
      if (!window.TradingView || !document.getElementById(uid.current)) return
      new window.TradingView.widget({
        autosize:          true,
        symbol:            symbol,
        interval:          "15",
        timezone:          "America/Phoenix",
        theme:             "dark",
        style:             "1",
        locale:            "en",
        enable_publishing: false,
        hide_top_toolbar:  false,
        hide_legend:       true,
        hide_side_toolbar: false,
        allow_symbol_change: true,
        save_image:        false,
        container_id:      uid.current,
        loading_screen:    { backgroundColor:"#0c0d10", foregroundColor:"#f5a623" },
        overrides: {
          "paneProperties.background":              "#0c0d10",
          "paneProperties.backgroundType":          "solid",
          "paneProperties.vertGridProperties.color":"#111318",
          "paneProperties.horzGridProperties.color":"#111318",
          "scalesProperties.textColor":             "#4e5462",
          "scalesProperties.backgroundColor":       "#0c0d10",
          "mainSeriesProperties.candleStyle.upColor":       "#3ecf8e",
          "mainSeriesProperties.candleStyle.downColor":     "#e05252",
          "mainSeriesProperties.candleStyle.borderUpColor": "#3ecf8e",
          "mainSeriesProperties.candleStyle.borderDownColor":"#e05252",
          "mainSeriesProperties.candleStyle.wickUpColor":   "#3ecf8e",
          "mainSeriesProperties.candleStyle.wickDownColor": "#e05252",
        },
        studies_overrides: {
          "volume.volume.color.0": "#e05252",
          "volume.volume.color.1": "#3ecf8e",
          "volume.volume ma.color": "#f5a623",
          "volume.volume ma.linewidth": 1,
        },
        custom_css_url: "",
        toolbar_bg: "#0c0d10",
      })
    }

    if (window.TradingView) {
      init()
    } else {
      const s = document.createElement("script")
      s.src = "https://s3.tradingview.com/tv.js"
      s.async = true
      s.onload = init
      document.head.appendChild(s)
    }
  }, [symbol])

  return (
    <div ref={ref} className="tv-wrap" style={{ height, minHeight: Math.min(height, 220) }} />
  )
}
