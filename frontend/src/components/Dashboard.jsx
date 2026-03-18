import React from "react"
import SignalCard from "./SignalCard"

const REGIME_BADGE = {
  TREND:    "bg-emerald-900/40 text-emerald-300 border-emerald-700/40",
  RANGE:    "bg-yellow-900/40 text-yellow-300 border-yellow-700/40",
  BREAKOUT: "bg-cyan-900/40 text-cyan-300 border-cyan-700/40",
  HIGH_VOL: "bg-purple-900/40 text-purple-300 border-purple-700/40",
}

function getRegimeKey(regime) {
  if (!regime) return null
  if (regime.startsWith("TREND")) return "TREND"
  if (regime.startsWith("BREAKOUT")) return "BREAKOUT"
  if (regime === "HIGH_VOL") return "HIGH_VOL"
  return "RANGE"
}

export default function Dashboard({ symbol, signal, tick }) {
  const price   = tick?.price ?? null
  const change  = tick?.change ?? null
  const changePct = tick?.change_pct ?? null
  const regime  = signal?.subscores ? null : signal?.regime   // from debug
  const regimeKey = getRegimeKey(regime)

  return (
    <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
      {/* Price card */}
      <div className="rounded-2xl border border-gray-200 dark:border-gray-700/60 bg-white/80 dark:bg-gray-800/50 backdrop-blur-sm p-4 flex flex-col justify-between">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold tracking-widest text-gray-400 uppercase">Symbol</span>
          {regimeKey && (
            <span className={`text-xs px-2 py-0.5 rounded-full border font-medium ${REGIME_BADGE[regimeKey]}`}>
              {regime}
            </span>
          )}
        </div>
        <div>
          <div className="text-3xl font-bold tracking-tight">{symbol}</div>
          {price != null ? (
            <div className="mt-1 flex items-baseline gap-2">
              <span className="text-2xl font-mono">${price.toFixed(2)}</span>
              {change != null && (
                <span className={`text-sm font-mono ${change >= 0 ? "text-emerald-400" : "text-red-400"}`}>
                  {change >= 0 ? "+" : ""}{change.toFixed(2)} ({changePct >= 0 ? "+" : ""}{changePct?.toFixed(2)}%)
                </span>
              )}
            </div>
          ) : (
            <div className="mt-1 text-xl font-mono text-gray-400">—</div>
          )}
        </div>
      </div>

      {/* Signal card spans 2 cols */}
      <div className="md:col-span-2">
        <SignalCard signal={signal} />
      </div>
    </div>
  )
}