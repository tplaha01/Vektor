import React from "react";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import AlfredDashboard from "./pages/AlfredDashboard";
import Admin from "./pages/Admin";
import Research from "./pages/Research";
import Blog from "./pages/Blog";
import "./styles/admin.css";
import "./styles/research.css";
import "./styles/blog.css";

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<AlfredDashboard />} />
        <Route path="/admin" element={<Admin />} />
        <Route path="/research" element={<Research />} />
        <Route path="/blog" element={<Blog />} />
      </Routes>
    </BrowserRouter>
  );
}
