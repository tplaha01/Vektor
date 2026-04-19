"use client";

export function TextHighlighter({ children, color = "var(--accent)" }) {
  return (
    <span
      style={{
        background: `linear-gradient(120deg, transparent 0%, ${color}33 50%, transparent 100%)`,
        backgroundSize: "200% 100%",
        backgroundPosition: "100% 0",
        animation: "shimmer 3s infinite",
        paddingInline: "0.2em",
      }}
    >
      {children}
    </span>
  );
}
