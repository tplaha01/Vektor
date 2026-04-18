import React from "react";

export default function NotFoundPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        display: "grid",
        placeItems: "center",
        background: "linear-gradient(160deg, #070a0f, #0f1724)",
        padding: 24,
      }}
    >
      <div style={{ textAlign: "center", maxWidth: 560 }}>
        <p className="label" style={{ marginBottom: 8 }}>Route not found</p>
        <h1 style={{ fontSize: 46, marginBottom: 10 }}>404</h1>
        <p style={{ color: "var(--txt2)", marginBottom: 16 }}>
          This page does not exist yet or has been moved.
        </p>
        <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
          <a className="btn btn-amber" href="/">Public PnL</a>
          <a className="btn btn-tab on" href="/admin">Admin Portal</a>
          <a className="btn btn-tab" href="/legacy">Legacy Workspace</a>
        </div>
      </div>
    </div>
  );
}
