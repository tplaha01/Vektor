"use client";

import React, { useEffect, useRef, useCallback, useState } from "react";
import { useTheme } from "next-themes";

/* ─────────────────────────────────────────────
   Animated Liquid Background  –  WebGL
   Subtle, slow-moving purple plasma glow.
   Adapts to dark / light theme.
   ───────────────────────────────────────────── */

const VERTEX = `
  attribute vec2 a_position;
  void main() { gl_Position = vec4(a_position, 0.0, 1.0); }
`;

const FRAGMENT = `
precision highp float;

uniform float u_time;
uniform vec2  u_resolution;
uniform vec3  u_color1;
uniform vec3  u_color2;
uniform vec3  u_bg;

// ---- 3D simplex noise ----
vec3 mod289(vec3 x){ return x - floor(x*(1.0/289.0))*289.0; }
vec4 mod289(vec4 x){ return x - floor(x*(1.0/289.0))*289.0; }
vec4 permute(vec4 x){ return mod289(((x*34.0)+1.0)*x); }
vec4 taylorInvSqrt(vec4 r){ return 1.79284291400159 - 0.85373472095314*r; }

float snoise(vec3 v){
  const vec2 C = vec2(1.0/6.0, 1.0/3.0);
  const vec4 D = vec4(0.0,0.5,1.0,2.0);
  vec3 i  = floor(v + dot(v, C.yyy));
  vec3 x0 = v - i + dot(i, C.xxx);
  vec3 g  = step(x0.yzx, x0.xyz);
  vec3 l  = 1.0 - g;
  vec3 i1 = min(g.xyz, l.zxy);
  vec3 i2 = max(g.xyz, l.zxy);
  vec3 x1 = x0 - i1 + C.xxx;
  vec3 x2 = x0 - i2 + C.yyy;
  vec3 x3 = x0 - D.yyy;
  i = mod289(i);
  vec4 p = permute(permute(permute(
    i.z + vec4(0.0, i1.z, i2.z, 1.0))
  + i.y + vec4(0.0, i1.y, i2.y, 1.0))
  + i.x + vec4(0.0, i1.x, i2.x, 1.0));
  float n_ = 0.142857142857;
  vec3 ns = n_ * D.wyz - D.xzx;
  vec4 j = p - 49.0*floor(p*ns.z*ns.z);
  vec4 x_ = floor(j*ns.z);
  vec4 y_ = floor(j - 7.0*x_);
  vec4 x  = x_*ns.x + ns.yyyy;
  vec4 y  = y_*ns.x + ns.yyyy;
  vec4 h  = 1.0 - abs(x) - abs(y);
  vec4 b0 = vec4(x.xy, y.xy);
  vec4 b1 = vec4(x.zw, y.zw);
  vec4 s0 = floor(b0)*2.0 + 1.0;
  vec4 s1 = floor(b1)*2.0 + 1.0;
  vec4 sh = -step(h, vec4(0.0));
  vec4 a0 = b0.xzyw + s0.xzyw*sh.xxyy;
  vec4 a1 = b1.xzyw + s1.xzyw*sh.zzww;
  vec3 p0 = vec3(a0.xy, h.x);
  vec3 p1 = vec3(a0.zw, h.y);
  vec3 p2 = vec3(a1.xy, h.z);
  vec3 p3 = vec3(a1.zw, h.w);
  vec4 norm = taylorInvSqrt(vec4(dot(p0,p0),dot(p1,p1),dot(p2,p2),dot(p3,p3)));
  p0 *= norm.x; p1 *= norm.y; p2 *= norm.z; p3 *= norm.w;
  vec4 m = max(0.6 - vec4(dot(x0,x0),dot(x1,x1),dot(x2,x2),dot(x3,x3)), 0.0);
  m = m*m;
  return 42.0 * dot(m*m, vec4(dot(p0,x0),dot(p1,x1),dot(p2,x2),dot(p3,x3)));
}

float fbm(vec3 p){
  float v = 0.0, a = 0.5;
  vec3 shift = vec3(100.0);
  for(int i=0; i<5; i++){
    v += a * snoise(p);
    p = p * 2.0 + shift;
    a *= 0.5;
  }
  return v;
}

void main(){
  vec2 uv = gl_FragCoord.xy / u_resolution.xy;
  float aspect = u_resolution.x / u_resolution.y;
  uv.x *= aspect;

  // Very slow time — dreamy, gentle motion
  float t = u_time * 0.04;

  vec3 p = vec3(uv * 1.6, t);

  // Double domain-warp for organic flow
  float q1 = fbm(p + vec3(1.7, 9.2, 0.0));
  float q2 = fbm(p + vec3(8.3, 2.8, 0.0));
  vec2 q  = vec2(q1, q2);

  float r1 = fbm(p + vec3(1.2 * q.x + 1.7, 1.3 * q.y + 9.2, t * 0.4));
  float r2 = fbm(p + vec3(8.3 * q.x + 8.3, 2.8 * q.y + 2.8, t * 0.3));
  vec2 r  = vec2(r1, r2);

  float f = fbm(p + vec3(3.5 * r, 0.0));

  // Build luminance - much brighter
  float lum = f * 0.5 + 0.5;
  lum = lum * lum * lum * lum;  // very aggressive contrast
  lum = smoothstep(0.0, 1.0, lum);

  float swirl = snoise(vec3(uv * 2.2 + r * 1.2, t * 0.25));
  swirl = swirl * 0.5 + 0.5;
  swirl = smoothstep(0.15, 0.85, swirl);

  // Mix glow colors onto the background - dimmed version
  float intensity = lum * swirl;
  vec3 glow = mix(u_color1, u_color2, swirl);
  // Reduced intensity for dimmer effect: 1.5x instead of 3.5x
  vec3 col = mix(u_bg, glow, clamp(intensity * 1.5, 0.0, 1.0));
  // Reduced highlight intensity from 2.0x to 1.0x
  col += glow * intensity * 1.0;

  // Soft vignette falloff (much lighter)
  vec2 vuv = gl_FragCoord.xy / u_resolution.xy;
  float vig = 1.0 - smoothstep(0.0, 1.5, length(vuv - 0.5) * 1.0);
  col = mix(col * 0.3, col, vig);

  gl_FragColor = vec4(col, 1.0);
}
`;

function hexToVec3(hex) {
  hex = hex.replace("#", "");
  return [
    parseInt(hex.substring(0, 2), 16) / 255,
    parseInt(hex.substring(2, 4), 16) / 255,
    parseInt(hex.substring(4, 6), 16) / 255,
  ];
}

function compileShader(gl, type, src) {
  const s = gl.createShader(type);
  gl.shaderSource(s, src);
  gl.compileShader(s);
  if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
    console.error("Shader error:", gl.getShaderInfoLog(s));
    gl.deleteShader(s);
    return null;
  }
  return s;
}

// Theme color palettes
const PALETTES = {
  dark: {
    bg: "#060608",
    color1: "#6B2FA0",  // deep purple
    color2: "#B566FF",  // vivid purple
  },
  light: {
    bg: "#f8fafc",
    color1: "#7c3800",  // soft lavender
    color2: "#570600",  // gentle purple
  },
};

export default function LiquidBackground() {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);
  const glRef = useRef(null);
  const uniformsRef = useRef(null);
  const { resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => { setMounted(true); }, []);

  // Update uniforms when theme changes (no re-init needed)
  useEffect(() => {
    if (!uniformsRef.current || !glRef.current) return;
    const gl = glRef.current;
    const loc = uniformsRef.current;
    const pal = PALETTES[resolvedTheme] || PALETTES.dark;

    gl.useProgram(loc._prog);
    gl.uniform3fv(loc.u_bg, hexToVec3(pal.bg));
    gl.uniform3fv(loc.u_color1, hexToVec3(pal.color1));
    gl.uniform3fv(loc.u_color2, hexToVec3(pal.color2));
  }, [resolvedTheme]);

  const boot = useCallback(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;

    const gl = cvs.getContext("webgl", {
      alpha: false, antialias: false,
      premultipliedAlpha: false, preserveDrawingBuffer: false,
    });
    if (!gl) {
      console.warn("WebGL not supported");
      return;
    }
    glRef.current = gl;

    const vs = compileShader(gl, gl.VERTEX_SHADER, VERTEX);
    const fs = compileShader(gl, gl.FRAGMENT_SHADER, FRAGMENT);
    if (!vs || !fs) return;

    const prog = gl.createProgram();
    gl.attachShader(prog, vs);
    gl.attachShader(prog, fs);
    gl.linkProgram(prog);
    if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) {
      console.error("Link error:", gl.getProgramInfoLog(prog));
      return;
    }

    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);

    const aPos = gl.getAttribLocation(prog, "a_position");
    const loc = {
      _prog: prog,
      u_time: gl.getUniformLocation(prog, "u_time"),
      u_resolution: gl.getUniformLocation(prog, "u_resolution"),
      u_color1: gl.getUniformLocation(prog, "u_color1"),
      u_color2: gl.getUniformLocation(prog, "u_color2"),
      u_bg: gl.getUniformLocation(prog, "u_bg"),
    };
    uniformsRef.current = loc;

    // Set initial palette
    const pal = PALETTES[resolvedTheme] || PALETTES.dark;
    gl.useProgram(prog);
    gl.uniform3fv(loc.u_bg, hexToVec3(pal.bg));
    gl.uniform3fv(loc.u_color1, hexToVec3(pal.color1));
    gl.uniform3fv(loc.u_color2, hexToVec3(pal.color2));

    const t0 = performance.now();

    function resize() {
      const dpr = window.devicePixelRatio || 1;
      const w = cvs.clientWidth;
      const h = cvs.clientHeight;
      if (w > 0 && h > 0) {
        cvs.width  = w * dpr;
        cvs.height = h * dpr;
        gl.viewport(0, 0, cvs.width, cvs.height);
      }
    }
    resize();
    window.addEventListener("resize", resize);

    function frame() {
      const t = (performance.now() - t0) / 1000;
      gl.useProgram(prog);
      gl.enableVertexAttribArray(aPos);
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
      gl.uniform1f(loc.u_time, t);
      gl.uniform2f(loc.u_resolution, cvs.width, cvs.height);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      rafRef.current = requestAnimationFrame(frame);
    }
    rafRef.current = requestAnimationFrame(frame);

    return () => {
      window.removeEventListener("resize", resize);
      cancelAnimationFrame(rafRef.current);
      gl.deleteProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      gl.deleteBuffer(buf);
      glRef.current = null;
      uniformsRef.current = null;
    };
  }, []); // intentionally no deps — palette updates handled via separate effect

  useEffect(() => {
    const cleanup = boot();
    return () => cleanup?.();
  }, [boot]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: 0,
        pointerEvents: "none",
      }}
      suppressHydrationWarning
    >
      <canvas
        ref={canvasRef}
        style={{
          width: "100%",
          height: "100%",
          display: "block",
          filter: "blur(10px)",
          opacity: 1.0,
        }}
      />
      {/* Subtle noise grain */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            'url("https://framerusercontent.com/images/g0QcWrxr87K0ufOxIUFBakwYA8.png")',
          backgroundSize: 200,
          backgroundRepeat: "repeat",
          opacity: 0.04,
          mixBlendMode: "overlay",
        }}
      />
    </div>
  );
}
