import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
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

export default function App() {
  return (
    <BrowserRouter>
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
