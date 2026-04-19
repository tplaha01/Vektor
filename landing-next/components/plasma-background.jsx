"use client";

import React, { useEffect, useState } from "react";
import { useTheme } from "next-themes";

// CSS-based animated plasma background with extreme visibility
export default function PlasmaBackground() {
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);
  
  // Only render after mounting to avoid hydration mismatch
  useEffect(() => {
    setMounted(true);
  }, []);
  
  if (!mounted) return null;
  
  // Theme-specific colors
  const isDark = resolvedTheme === "dark";
  const colors = isDark
    ? {
        primary: "#B566FF",     // Vivid purple
        secondary: "#6B2FA0",   // Deep purple
        accent: "#FF00FF",      // Hot magenta
        bg: "#060608"
      }
    : {
        primary: "#9B7FE8",     // Gentle purple
        secondary: "#C4A0F0",   // Soft lavender
        accent: "#A855F7",      // Bright purple
        bg: "#f8fafc"
      };

  const style = `
    @keyframes plasma-float-1 {
      0% { transform: translate(0, 0) scale(1); }
      25% { transform: translate(30px, -40px) scale(1.1); }
      50% { transform: translate(-20px, 20px) scale(0.9); }
      75% { transform: translate(40px, 30px) scale(1.05); }
      100% { transform: translate(0, 0) scale(1); }
    }
    
    @keyframes plasma-float-2 {
      0% { transform: translate(0, 0) scale(1); }
      25% { transform: translate(-40px, 30px) scale(0.95); }
      50% { transform: translate(20px, -20px) scale(1.08); }
      75% { transform: translate(-30px, -40px) scale(1.02); }
      100% { transform: translate(0, 0) scale(1); }
    }
    
    @keyframes plasma-glow {
      0%, 100% { opacity: 0.6; filter: blur(60px) brightness(1); }
      50% { opacity: 0.9; filter: blur(40px) brightness(1.3); }
    }
    
    .plasma-bg {
      position: fixed;
      top: 0;
      left: 0;
      width: 100%;
      height: 100%;
      z-index: 0;
      pointer-events: none;
      overflow: hidden;
    }
    
    .plasma-orb {
      position: absolute;
      border-radius: 50%;
      filter: blur(80px);
      opacity: 0.7;
      mix-blend-mode: screen;
    }
    
    .orb-1 {
      width: 400px;
      height: 400px;
      top: -100px;
      left: -100px;
      background: radial-gradient(circle, ${colors.primary} 0%, transparent 70%);
      animation: plasma-float-1 8s ease-in-out infinite, plasma-glow 4s ease-in-out infinite;
    }
    
    .orb-2 {
      width: 350px;
      height: 350px;
      top: 50%;
      right: -50px;
      background: radial-gradient(circle, ${colors.secondary} 0%, transparent 70%);
      animation: plasma-float-2 7s ease-in-out infinite, plasma-glow 5s ease-in-out infinite 1s;
    }
    
    .orb-3 {
      width: 320px;
      height: 320px;
      bottom: -80px;
      left: 30%;
      background: radial-gradient(circle, ${colors.accent} 0%, transparent 70%);
      animation: plasma-float-1 9s ease-in-out infinite, plasma-glow 6s ease-in-out infinite 2s;
      opacity: 0.5;
    }
    
    .plasma-overlay {
      position: absolute;
      width: 100%;
      height: 100%;
      background: radial-gradient(ellipse at center, transparent 0%, ${colors.bg} 100%);
      pointer-events: none;
    }
  `;

  return (
    <>
      <style>{style}</style>
      <div className="plasma-bg">
        <div className="orb-1"></div>
        <div className="orb-2"></div>
        <div className="orb-3"></div>
        <div className="plasma-overlay"></div>
      </div>
    </>
  );
}
