import { ImageResponse } from "next/og";

export const runtime = "edge";

function readParam(request: Request, key: string, fallback = ""): string {
  const value = new URL(request.url).searchParams.get(key);
  return String(value || fallback).trim();
}

function classifyVariant(category: string, assetClass: string, variant: string) {
  const combined = `${variant} ${category} ${assetClass}`.toLowerCase();
  if (combined.includes("premarket")) return "premarket";
  if (combined.includes("postmarket")) return "postmarket";
  if (combined.includes("commodity")) return "commodity";
  if (combined.includes("forex")) return "forex";
  if (combined.includes("crypto")) return "crypto";
  if (combined.includes("macro")) return "macro";
  if (combined.includes("multi_signal")) return "multi_signal";
  if (combined.includes("quant")) return "quant";
  if (combined.includes("technical")) return "technical";
  if (combined.includes("fundamental")) return "fundamental";
  if (combined.includes("sentiment")) return "sentiment";
  return "research";
}

function pickPalette(variant: string) {
  const map: Record<string, { bg: string; panel: string; accent: string; accent2: string; rail: string; chip: string }> = {
    premarket: { bg: "#07111f", panel: "#10243f", accent: "#7dd3fc", accent2: "#60a5fa", rail: "#38bdf8", chip: "#dbeafe" },
    postmarket: { bg: "#140c1f", panel: "#2a173f", accent: "#f59e0b", accent2: "#f97316", rail: "#fb7185", chip: "#ffedd5" },
    commodity: { bg: "#161109", panel: "#3c2712", accent: "#fbbf24", accent2: "#f59e0b", rail: "#f59e0b", chip: "#fef3c7" },
    forex: { bg: "#071917", panel: "#11332f", accent: "#2dd4bf", accent2: "#14b8a6", rail: "#14b8a6", chip: "#ccfbf1" },
    crypto: { bg: "#120d20", panel: "#2e1c52", accent: "#a78bfa", accent2: "#8b5cf6", rail: "#8b5cf6", chip: "#ede9fe" },
    macro: { bg: "#10131d", panel: "#27314d", accent: "#c084fc", accent2: "#818cf8", rail: "#a78bfa", chip: "#ede9fe" },
    multi_signal: { bg: "#081419", panel: "#133943", accent: "#34d399", accent2: "#60a5fa", rail: "#22d3ee", chip: "#ccfbf1" },
    quant: { bg: "#08131a", panel: "#12313e", accent: "#22d3ee", accent2: "#10b981", rail: "#22c55e", chip: "#dcfce7" },
    technical: { bg: "#0b1320", panel: "#17335f", accent: "#60a5fa", accent2: "#38bdf8", rail: "#60a5fa", chip: "#dbeafe" },
    fundamental: { bg: "#12150b", panel: "#33451b", accent: "#84cc16", accent2: "#65a30d", rail: "#84cc16", chip: "#ecfccb" },
    sentiment: { bg: "#1a0a14", panel: "#4b1635", accent: "#f472b6", accent2: "#ec4899", rail: "#f472b6", chip: "#fce7f3" },
    research: { bg: "#08131a", panel: "#12313e", accent: "#34d399", accent2: "#22c55e", rail: "#34d399", chip: "#dcfce7" },
  };
  return map[variant] || map.research;
}

function pickLanes(variant: string, primarySymbol: string) {
  const symbol = primarySymbol || "MULTI-ASSET";
  const lanes: Record<string, string[]> = {
    premarket: ["Overnight flow", "Opening range", "Risk carry"],
    postmarket: ["Closing tone", "Leaders/laggards", "Tomorrow setup"],
    commodity: [symbol, "Supply / demand", "Cross-asset pressure"],
    forex: [symbol, "Rates spread", "Macro catalyst"],
    crypto: [symbol, "Risk appetite", "Liquidity regime"],
    macro: ["Macro calendar", "Rates impulse", "Cross-asset map"],
    multi_signal: [symbol, "Signal fusion", "Execution plan"],
    quant: [symbol, "Signal quality", "Model drift"],
    technical: [symbol, "Structure", "Momentum"],
    fundamental: [symbol, "Valuation", "Catalyst map"],
    sentiment: [symbol, "Narrative", "Crowding"],
    research: [symbol, "Evidence stack", "Execution discipline"],
  };
  return lanes[variant] || lanes.research;
}

export async function GET(request: Request) {
  const title = readParam(request, "title", "Vektor Market Brief");
  const subtitle = readParam(request, "subtitle", "AI-native market intelligence");
  const category = readParam(request, "category", "");
  const assetClass = readParam(request, "assetClass", "");
  const primarySymbol = readParam(request, "primarySymbol", "");
  const variant = classifyVariant(category, assetClass, readParam(request, "variant", "market"));
  const eyebrow = readParam(request, "eyebrow", "VEKTOR");
  const symbols = readParam(request, "symbols", "SPY / QQQ / NVDA");
  const palette = pickPalette(variant);
  const lanes = pickLanes(variant, primarySymbol);

  return new ImageResponse(
    (
      <div
        style={{
          width: "1200px",
          height: "630px",
          display: "flex",
          background: `linear-gradient(135deg, ${palette.bg} 0%, #020617 68%, ${palette.panel} 100%)`,
          color: "white",
          padding: "40px",
          fontFamily: "system-ui, sans-serif",
        }}
      >
        <div
          style={{
            display: "flex",
            flex: 1,
            border: `1px solid ${palette.panel}`,
            borderRadius: "28px",
            padding: "42px",
            background: "rgba(2,6,23,0.72)",
            position: "relative",
            overflow: "hidden",
          }}
        >
          <div
            style={{
              position: "absolute",
              top: "-80px",
              right: "-40px",
              width: "340px",
              height: "340px",
              borderRadius: "999px",
              background: `radial-gradient(circle, ${palette.accent}55 0%, transparent 70%)`,
            }}
          />
          <div
            style={{
              position: "absolute",
              bottom: "-90px",
              left: "-10px",
              width: "280px",
              height: "280px",
              borderRadius: "999px",
              background: `radial-gradient(circle, ${palette.accent2}44 0%, transparent 70%)`,
            }}
          />
          <div
            style={{
              position: "absolute",
              right: "38px",
              top: "34px",
              display: "flex",
              flexDirection: "column",
              gap: "10px",
              width: "220px",
            }}
          >
            {lanes.map((lane) => (
              <div
                key={lane}
                style={{
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "space-between",
                  padding: "12px 14px",
                  borderRadius: "16px",
                  border: `1px solid ${palette.panel}`,
                  background: "rgba(15,23,42,0.72)",
                  fontSize: "18px",
                  color: "#e2e8f0",
                }}
              >
                <span>{lane}</span>
                <span style={{ color: palette.rail }}>•</span>
              </div>
            ))}
          </div>
          <div style={{ display: "flex", flexDirection: "column", justifyContent: "space-between", flex: 1 }}>
            <div style={{ display: "flex", flexDirection: "column", gap: "22px", maxWidth: "760px" }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: "12px",
                  fontSize: "24px",
                  letterSpacing: "0.18em",
                  color: "#cbd5e1",
                }}
              >
                <div
                  style={{
                    width: "14px",
                    height: "14px",
                    borderRadius: "999px",
                    background: palette.accent,
                  }}
                />
                <span>{eyebrow.toUpperCase()}</span>
              </div>
              <div style={{ fontSize: "68px", lineHeight: 1.02, fontWeight: 800 }}>{title}</div>
              <div style={{ fontSize: "30px", lineHeight: 1.3, color: "#dbeafe", maxWidth: "720px" }}>{subtitle}</div>
            </div>

            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-end" }}>
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  gap: "12px",
                  padding: "18px 22px",
                  borderRadius: "20px",
                  border: `1px solid ${palette.panel}`,
                  background: "rgba(15,23,42,0.88)",
                  minWidth: "340px",
                }}
              >
                <div style={{ fontSize: "18px", letterSpacing: "0.14em", color: "#94a3b8" }}>TRACKING</div>
                <div style={{ fontSize: "28px", color: "#f8fafc" }}>{symbols}</div>
              </div>
              <div
                style={{
                  fontSize: "18px",
                  color: palette.chip,
                  letterSpacing: "0.16em",
                  textTransform: "uppercase",
                }}
              >
                {assetClass || category || "Research Desk"}
              </div>
            </div>
          </div>
        </div>
      </div>
    ),
    { width: 1200, height: 630 }
  );
}
