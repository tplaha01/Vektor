import React, { useEffect } from "react";
import { BrowserRouter, Routes, Route, useLocation } from "react-router-dom";
import AlfredDashboard from "./pages/AlfredDashboard";
import Admin from "./pages/Admin";
import Research from "./pages/Research";
import Blog from "./pages/Blog";
import AuditTrail from "./pages/AuditTrail";
import ThesisDetail from "./pages/ThesisDetail";
import PublicPnlPage from "./pages/PublicPnlPage";
import NotFoundPage from "./pages/NotFoundPage";
import "./styles/admin.css";
import "./styles/research.css";
import "./styles/blog.css";
import "./styles/audit.css";
import "./styles/thesis.css";

function RouteTitleManager() {
  const location = useLocation();

  useEffect(() => {
    const path = location.pathname || "/";
    let title = "Vektor";

    if (path === "/") title = "Vektor - Live PnL";
    else if (path === "/admin") title = "Vektor - Admin";
    else if (path === "/research") title = "Vektor - Research";
    else if (path === "/blog") title = "Vektor - Blog";
    else if (path === "/legacy") title = "Vektor - Legacy";
    else if (path.startsWith("/audit/")) title = "Vektor - Audit";
    else if (path.startsWith("/thesis/")) title = "Vektor - Thesis";
    else title = "Vektor - Workspace";

    document.title = title;
  }, [location.pathname]);

  return null;
}

export default function App() {
  return (
    <BrowserRouter>
      <RouteTitleManager />
      <Routes>
        <Route path="/" element={<PublicPnlPage />} />
        <Route path="/legacy" element={<AlfredDashboard />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/research" element={<Research />} />
        <Route path="/blog" element={<Blog />} />
        <Route path="/audit/:decisionId" element={<AuditTrail />} />
        <Route path="/thesis/:thesisId" element={<ThesisDetail />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </BrowserRouter>
  );
}
