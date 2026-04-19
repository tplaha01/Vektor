"use client";

import React, { useEffect, useRef, useCallback } from "react";

/* ─────────────────────────────────────────────
   Animated Liquid Background  –  pure WebGL
   Replicates the Framer "AnimatedLiquidBackground" warp shader.
   Zero external dependencies beyond React.
   ───────────────────────────────────────────── */

const VERTEX_SRC = `
  attribute vec2 a_position;
  void main() {
    gl_Position = vec4(a_position, 0.0, 1.0);
  }
`;

const FRAGMENT_SRC = `
  precision highp float;

  uniform float u_time;
  uniform vec2  u_resolution;

  uniform vec3  u_color1;
  uniform vec3  u_color2;
  uniform vec3  u_color3;

  uniform float u_speed;
  uniform float u_scale;
  uniform float u_proportion;
  uniform float u_softness;
  uniform float u_distortion;
  uniform float u_swirl;
  uniform int   u_swirlIterations;
  uniform float u_rotation;
  uniform float u_seed;
  uniform float u_shapeScale;

  // --- helpers ---
  mat2 rot(float a) {
    float s = sin(a), c = cos(a);
    return mat2(c, -s, s, c);
  }

  float hash(vec2 p) {
    return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
  }

  float noise(vec2 p) {
    vec2 i = floor(p);
    vec2 f = fract(p);
    f = f * f * (3.0 - 2.0 * f);
    float a = hash(i);
    float b = hash(i + vec2(1.0, 0.0));
    float c = hash(i + vec2(0.0, 1.0));
    float d = hash(i + vec2(1.0, 1.0));
    return mix(mix(a, b, f.x), mix(c, d, f.x), f.y);
  }

  float fbm(vec2 p) {
    float v = 0.0, a = 0.5;
    for (int i = 0; i < 6; i++) {
      v += a * noise(p);
      p = p * 2.0 + vec2(1.7, 9.2);
      a *= 0.5;
    }
    return v;
  }

  vec2 swirlWarp(vec2 uv, float t) {
    vec2 p = uv;
    for (int i = 0; i < 20; i++) {
      if (i >= u_swirlIterations) break;
      p += u_swirl * 0.3 * vec2(
        sin(p.y * 2.5 + t * 0.7 + float(i) * 0.5),
        cos(p.x * 2.5 + t * 0.6 + float(i) * 0.5)
      ) / float(u_swirlIterations);
    }
    return p;
  }

  // --- checks / shape pattern ---
  float pattern(vec2 uv) {
    vec2 grid = fract(uv * (1.0 + u_shapeScale * 10.0));
    float checks = step(0.5, grid.x) * step(0.5, grid.y)
                 + step(0.5, 1.0 - grid.x) * step(0.5, 1.0 - grid.y);
    return mix(1.0, checks, u_shapeScale);
  }

  void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    float aspect = u_resolution.x / u_resolution.y;
    uv.x *= aspect;

    float t = u_time * u_speed;

    // apply rotation
    vec2 center = vec2(0.5 * aspect, 0.5);
    uv = (uv - center) * rot(u_rotation) + center;

    // offset / seed
    uv += u_seed * 0.001;

    // scale
    uv = (uv - center) * (1.0 + u_scale * 3.0) + center;

    // distortion via FBM
    vec2 distort = vec2(
      fbm(uv * 3.0 + t * 0.15),
      fbm(uv * 3.0 + t * 0.15 + vec2(5.2, 1.3))
    );
    uv += distort * u_distortion * 0.5;

    // swirl warp
    uv = swirlWarp(uv, t);

    // generate smooth fields
    float field1 = fbm(uv * 2.0 + t * 0.08);
    float field2 = fbm(uv * 1.5 - t * 0.12 + vec2(3.1, 7.4));
    float field3 = fbm(uv * 3.5 + t * 0.05 + vec2(9.2, 2.8));

    float mix1 = smoothstep(0.3 - u_softness * 0.3, 0.7 + u_softness * 0.3, field1);
    float mix2 = smoothstep(0.4 - u_softness * 0.3, 0.6 + u_softness * 0.3, field2);
    float mix3 = smoothstep(0.35, 0.65, field3);

    // proportion influences blending
    float prop = u_proportion;

    vec3 col = u_color1;
    col = mix(col, u_color2, mix1 * (1.0 - prop * 0.5));
    col = mix(col, u_color3, mix2 * prop * 0.6);
    col = mix(col, u_color1 * 0.8 + u_color2 * 0.2, mix3 * 0.3);

    // subtle pattern overlay
    float p = pattern(uv);
    col *= 0.9 + 0.1 * p;

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

function createShader(gl, type, src) {
  const shader = gl.createShader(type);
  gl.shaderSource(shader, src);
  gl.compileShader(shader);
  if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
    console.error("Shader compile error:", gl.getShaderInfoLog(shader));
    gl.deleteShader(shader);
    return null;
  }
  return shader;
}

function createProgram(gl, vs, fs) {
  const program = gl.createProgram();
  gl.attachShader(program, vs);
  gl.attachShader(program, fs);
  gl.linkProgram(program);
  if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
    console.error("Program link error:", gl.getProgramInfoLog(program));
    gl.deleteProgram(program);
    return null;
  }
  return program;
}

// Preset configs matching the Framer component
const PRESETS = {
  Prism: {
    color1: "#050505", color2: "#66B3FF", color3: "#FFFFFF",
    rotation: -50, proportion: 1, scale: 0.01, speed: 30,
    distortion: 0, swirl: 50, swirlIterations: 16,
    softness: 47, offset: -299, shapeSize: 45,
  },
  Lava: {
    color1: "#FF9F21", color2: "#FF0303", color3: "#000000",
    rotation: 114, proportion: 100, scale: 0.52, speed: 30,
    distortion: 7, swirl: 18, swirlIterations: 20,
    softness: 100, offset: 717, shapeSize: 12,
  },
  Plasma: {
    color1: "#B566FF", color2: "#000000", color3: "#000000",
    rotation: 0, proportion: 63, scale: 0.75, speed: 30,
    distortion: 5, swirl: 61, swirlIterations: 5,
    softness: 100, offset: -168, shapeSize: 28,
  },
  Pulse: {
    color1: "#66FF85", color2: "#000000", color3: "#000000",
    rotation: -167, proportion: 92, scale: 0, speed: 20,
    distortion: 54, swirl: 75, swirlIterations: 3,
    softness: 28, offset: -813, shapeSize: 79,
  },
  Vortex: {
    color1: "#000000", color2: "#FFFFFF", color3: "#000000",
    rotation: 50, proportion: 41, scale: 0.4, speed: 20,
    distortion: 0, swirl: 100, swirlIterations: 3,
    softness: 5, offset: -744, shapeSize: 80,
  },
  Mist: {
    color1: "#050505", color2: "#FF66B8", color3: "#050505",
    rotation: 0, proportion: 33, scale: 0.48, speed: 39,
    distortion: 4, swirl: 65, swirlIterations: 5,
    softness: 100, offset: -235, shapeSize: 48,
  },
};

export default function LiquidBackground({
  preset = "Mist",
  speed: speedOverride,
  opacity = 0.45,
  noiseOpacity = 0.08,
  noiseScale = 1,
}) {
  const canvasRef = useRef(null);
  const animRef = useRef(null);

  const init = useCallback(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const gl = canvas.getContext("webgl", { alpha: true, antialias: false, premultipliedAlpha: false });
    if (!gl) { console.warn("WebGL not supported"); return; }

    const vs = createShader(gl, gl.VERTEX_SHADER, VERTEX_SRC);
    const fs = createShader(gl, gl.FRAGMENT_SHADER, FRAGMENT_SRC);
    if (!vs || !fs) return;

    const program = createProgram(gl, vs, fs);
    if (!program) return;

    // full-screen quad
    const buf = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buf);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1,-1, 1,-1, -1,1, 1,1]), gl.STATIC_DRAW);

    const aPos = gl.getAttribLocation(program, "a_position");

    // uniforms
    const loc = {};
    [
      "u_time","u_resolution","u_color1","u_color2","u_color3",
      "u_speed","u_scale","u_proportion","u_softness","u_distortion",
      "u_swirl","u_swirlIterations","u_rotation","u_seed","u_shapeScale",
    ].forEach((name) => { loc[name] = gl.getUniformLocation(program, name); });

    const cfg = PRESETS[preset] || PRESETS.Mist;
    const spd = speedOverride != null ? speedOverride : cfg.speed;

    const c1 = hexToVec3(cfg.color1);
    const c2 = hexToVec3(cfg.color2);
    const c3 = hexToVec3(cfg.color3);

    let startTime = performance.now();

    function resize() {
      const dpr = Math.min(window.devicePixelRatio || 1, 1.5); // cap for perf
      canvas.width = canvas.clientWidth * dpr;
      canvas.height = canvas.clientHeight * dpr;
      gl.viewport(0, 0, canvas.width, canvas.height);
    }
    resize();
    window.addEventListener("resize", resize);

    function frame() {
      const t = (performance.now() - startTime) / 1000;

      gl.useProgram(program);

      gl.enableVertexAttribArray(aPos);
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.vertexAttribPointer(aPos, 2, gl.FLOAT, false, 0, 0);

      gl.uniform1f(loc.u_time, t);
      gl.uniform2f(loc.u_resolution, canvas.width, canvas.height);
      gl.uniform3fv(loc.u_color1, c1);
      gl.uniform3fv(loc.u_color2, c2);
      gl.uniform3fv(loc.u_color3, c3);
      gl.uniform1f(loc.u_speed, spd / 100);
      gl.uniform1f(loc.u_scale, cfg.scale);
      gl.uniform1f(loc.u_proportion, cfg.proportion / 100);
      gl.uniform1f(loc.u_softness, cfg.softness / 100);
      gl.uniform1f(loc.u_distortion, cfg.distortion / 50);
      gl.uniform1f(loc.u_swirl, cfg.swirl / 100);
      gl.uniform1i(loc.u_swirlIterations, cfg.swirl === 0 ? 0 : cfg.swirlIterations);
      gl.uniform1f(loc.u_rotation, (cfg.rotation * Math.PI) / 180);
      gl.uniform1f(loc.u_seed, cfg.offset * 10);
      gl.uniform1f(loc.u_shapeScale, cfg.shapeSize / 100);

      gl.drawArrays(gl.TRIANGLE_STRIP, 0, 4);
      animRef.current = requestAnimationFrame(frame);
    }

    animRef.current = requestAnimationFrame(frame);

    return () => {
      window.removeEventListener("resize", resize);
      if (animRef.current) cancelAnimationFrame(animRef.current);
      gl.deleteProgram(program);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      gl.deleteBuffer(buf);
    };
  }, [preset, speedOverride]);

  useEffect(() => {
    const cleanup = init();
    return () => cleanup?.();
  }, [init]);

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        zIndex: -1,
        pointerEvents: "none",
        opacity,
      }}
    >
      <canvas
        ref={canvasRef}
        style={{ width: "100%", height: "100%", display: "block" }}
      />
      {/* Noise grain overlay */}
      {noiseOpacity > 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            backgroundImage:
              'url("https://framerusercontent.com/images/g0QcWrxr87K0ufOxIUFBakwYA8.png")',
            backgroundSize: noiseScale * 200,
            backgroundRepeat: "repeat",
            opacity: noiseOpacity,
            mixBlendMode: "overlay",
          }}
        />
      )}
    </div>
  );
}
