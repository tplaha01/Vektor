import React from "react";
import WorkspaceNav from "../components/common/WorkspaceNav";

export default function NotFoundPage() {
  return (
    <div
      style={{
        minHeight: "100vh",
        background: "linear-gradient(160deg, #070a0f, #0f1724)",
        padding: 24,
      }}
    >
      <div style={{ maxWidth: 1120, margin: "0 auto", display: "grid", gap: 18 }}>
        <WorkspaceNav
          eyebrow="Vektor Workspace"
          title="Route Not Found"
          summary="This surface does not exist yet or has moved. Use the workspace routes below to return to a live operator page."
        />
        <div className="panel panel-pad" style={{ textAlign: "center", padding: "48px 24px" }}>
          <p className="label" style={{ marginBottom: 8 }}>Missing route</p>
          <h1 style={{ fontSize: 56, marginBottom: 10 }}>404</h1>
          <p style={{ color: "var(--txt2)", marginBottom: 18, maxWidth: 520, marginInline: "auto" }}>
            The requested page is not available in the current local workspace build.
          </p>
          <div style={{ display: "flex", gap: 10, justifyContent: "center", flexWrap: "wrap" }}>
            <a className="btn btn-amber" href="/">Live PnL</a>
            <a className="btn btn-tab on" href="/admin">Admin</a>
            <a className="btn btn-tab" href="/research">Research</a>
            <a className="btn btn-tab" href="/blog">Blog</a>
            <a className="btn btn-tab" href="/legacy">Legacy</a>
          </div>
        </div>
      </div>
    </div>
  );
}
