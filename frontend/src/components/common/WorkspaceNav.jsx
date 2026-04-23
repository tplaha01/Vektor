import React from "react";
import { NavLink } from "react-router-dom";

const DEFAULT_LINKS = [
  { to: "/", label: "Live PnL" },
  { to: "/research", label: "Research" },
  { to: "/blog", label: "Blog" },
  { to: "/admin", label: "Admin" },
  { to: "/legacy", label: "Legacy" },
];

export default function WorkspaceNav({
  eyebrow = "Vektor Workspace",
  title = "Operator Surface",
  summary = "",
  meta = null,
  links = DEFAULT_LINKS,
  compact = false,
}) {
  return (
    <section className={`workspace-nav ${compact ? "workspace-nav-compact" : ""}`}>
      <div className="workspace-nav-brand">
        <img
          src="/VektorLogo.png?v=20260422b"
          alt="Vektor"
          className="workspace-nav-logo"
        />
        <div className="workspace-nav-copy">
          <div className="workspace-nav-eyebrow">{eyebrow}</div>
          <h1 className="workspace-nav-title">{title}</h1>
          {summary ? <p className="workspace-nav-summary">{summary}</p> : null}
        </div>
      </div>
      <div className="workspace-nav-links" aria-label="Workspace routes">
        {links.map((link) => (
          <NavLink
            key={link.to}
            to={link.to}
            end={link.to === "/"}
            className={({ isActive }) =>
              `workspace-nav-link ${isActive ? "is-active" : ""}`
            }
          >
            {link.label}
          </NavLink>
        ))}
      </div>
      {meta ? <div className="workspace-nav-meta">{meta}</div> : null}
    </section>
  );
}
