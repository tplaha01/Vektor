import React from "react";

export default function AppErrorPage({ error, onRetry }) {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        padding: 24,
        background: "radial-gradient(circle at 20% 20%, rgba(74,158,255,0.18), transparent 45%), var(--bg0)",
      }}
    >
      <div
        style={{
          maxWidth: 760,
          width: "100%",
          border: "1px solid var(--line2)",
          borderRadius: 14,
          background: "var(--bg1)",
          padding: 28,
          boxShadow: "0 18px 44px rgba(0,0,0,0.35)",
        }}
      >
        <h1 style={{ marginBottom: 10, fontSize: 28 }}>Something broke in the interface</h1>
        <p style={{ color: "var(--txt2)", marginBottom: 16 }}>
          The backend can still be healthy, but this screen hit an unexpected UI error.
          You can retry immediately without restarting the app.
        </p>
        <pre
          style={{
            background: "var(--bg2)",
            border: "1px solid var(--line)",
            borderRadius: 10,
            padding: 12,
            maxHeight: 200,
            overflow: "auto",
            color: "var(--txt2)",
          }}
        >
          {(error && (error.stack || error.message)) || "Unknown UI error"}
        </pre>
        <div style={{ display: "flex", gap: 10, marginTop: 16 }}>
          <button className="btn btn-amber" onClick={onRetry}>Retry UI</button>
          <a className="btn btn-tab on" href="/">Go to Public PnL</a>
          <a className="btn btn-tab" href="/legacy">Open Legacy Workspace</a>
        </div>
      </div>
    </div>
  );
}
