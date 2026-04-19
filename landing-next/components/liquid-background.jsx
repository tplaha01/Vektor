"use client";

import React, { useEffect, useRef, useCallback } from "react";

/* ─────────────────────────────────────────────
   Animated Liquid / Plasma Background  –  WebGL
   Replicates the Framer "Plasma" preset:
   Vivid purple organic blobs flowing on black.
   ───────────────────────────────────────────── */

const VERTEX = `
  attribute vec2 a_position;
  void main() { gl_Position = vec4(a_position, 0.0, 1.0); }
`;

// Plasma shader — smooth organic purple luminance on black
const FRAGMENT = `
precision highp float;

uniform float u_time;
uniform vec2  u_resolution;

// ---- noise helpers ----
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

  float t = u_time * 0.12;

  // Domain warping — creates the organic flowing shapes
  vec3 p = vec3(uv * 1.8, t);

  // First warp layer
  float q1 = fbm(p + vec3(1.7, 9.2, 0.0));
  float q2 = fbm(p + vec3(8.3, 2.8, 0.0));
  vec2 q  = vec2(q1, q2);

  // Second warp layer — produces the swirling motion
  float r1 = fbm(p + vec3(1.2 * q.x + 1.7, 1.3 * q.y + 9.2, t * 0.5));
  float r2 = fbm(p + vec3(8.3 * q.x + 8.3, 2.8 * q.y + 2.8, t * 0.4));
  vec2 r  = vec2(r1, r2);

  // Final warp
  float f = fbm(p + vec3(4.0 * r, 0.0));

  // Build the color
  // Plasma palette: purple (#B566FF) on black
  vec3 purple = vec3(0.710, 0.400, 1.000);   // #B566FF
  vec3 deepPurple = vec3(0.400, 0.100, 0.700);
  vec3 black = vec3(0.020, 0.020, 0.020);

  // Map noise to luminance — create big soft glowing regions
  float luminance = f * 0.5 + 0.5;
  luminance = luminance * luminance; // increase contrast
  luminance = smoothstep(0.15, 0.85, luminance);

  // Secondary swirl for variation
  float swirl = snoise(vec3(uv * 2.5 + r * 1.5, t * 0.3));
  swirl = swirl * 0.5 + 0.5;
  swirl = smoothstep(0.2, 0.8, swirl);

  // Mix colors
  vec3 col = mix(black, deepPurple, luminance * 0.6);
  col = mix(col, purple, luminance * swirl * 0.8);

  // Add bright highlights in the most intense areas
  float highlight = smoothstep(0.6, 1.0, luminance * swirl);
  col += purple * highlight * 0.5;

  // Subtle vignette to frame the effect
  vec2 vuv = gl_FragCoord.xy / u_resolution.xy;
  float vig = 1.0 - smoothstep(0.4, 1.4, length(vuv - 0.5) * 1.4);
  col *= mix(0.6, 1.0, vig);

  gl_FragColor = vec4(col, 1.0);
}
`;

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

export default function LiquidBackground() {
  const canvasRef = useRef(null);
  const rafRef = useRef(null);

  const boot = useCallback(() => {
    const cvs = canvasRef.current;
    if (!cvs) return;

    const gl = cvs.getContext("webgl", {
      alpha: false,
      antialias: false,
      premultipliedAlpha: false,
      preserveDrawingBuffer: false,
    });
    if (!gl) return;

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
    const uTime = gl.getUniformLocation(prog, "u_time");
    const uRes  = gl.getUniformLocation(prog, "u_resolution");

    const t0 = performance.now();

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5);
      cvs.width  = cvs.clientWidth  * dpr;
      cvs.height = cvs.clientHeight * dpr;
      gl.viewport(0, 0, cvs.width, cvs.height);
    }
    resize();
    const onResize = () => resize();
    window.addEventListener("resize", onResize);

    function frame() {
      const t = (performance.now() - t0) / 1000;
      gl.useProgram(prog);
      gl.enableVertexAttribArray(aPos);
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);
      gl.uniform1f(uTime, t);
      gl.uniform2f(uRes, cvs.width, cvs.height);
      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      rafRef.current = requestAnimationFrame(frame);
    }
    rafRef.current = requestAnimationFrame(frame);

    return () => {
      window.removeEventListener("resize", onResize);
      cancelAnimationFrame(rafRef.current);
      gl.deleteProgram(prog);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      gl.deleteBuffer(buf);
    };
  }, []);

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
    >
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", display: "block" }}
      />
      {/* Noise grain overlay */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          backgroundImage:
            'url("https://framerusercontent.com/images/g0QcWrxr87K0ufOxIUFBakwYA8.png")',
          backgroundSize: 200,
          backgroundRepeat: "repeat",
          opacity: 0.06,
          mixBlendMode: "overlay",
        }}
      />
    </div>
  );
}
