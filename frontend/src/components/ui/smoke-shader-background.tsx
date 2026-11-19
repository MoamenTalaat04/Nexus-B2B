"use client";

import { useTheme } from "next-themes";
import { useEffect, useRef, useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";

type ThemeMode = "light" | "dark";

export interface SmokeShaderBackgroundProps {
  /** Optional explicit theme override; defaults to the active NEXUS theme. */
  theme?: ThemeMode;
  className?: string;
}

const emptySubscribe = () => () => {};

// Smoke is all soft gradients, so render small and let the browser upscale it.
const RENDER_SCALE = 0.4;

const VERT = `attribute vec2 a;void main(){gl_Position=vec4(a,0.,1.);}`;

const FRAG = `
precision mediump float;
uniform float u_time;
uniform vec2 u_resolution;
uniform float u_dark;

void main() {
  vec2 uv = gl_FragCoord.xy / u_resolution.xy;

  // Domain warping for fluid "stream" motion
  for (float i = 1.0; i < 4.0; i++) {
    uv.x += 0.35 / i * sin(i * 3.0 * uv.y + u_time * 0.4);
    uv.y += 0.35 / i * cos(i * 3.0 * uv.x + u_time * 0.3);
  }

  float wave = 0.5 + 0.5 * cos(u_time * 0.2 + uv.x * 2.4 + uv.y * 2.0);
  float accent = 0.5 + 0.5 * sin(u_time * 0.18 + uv.y * 3.0 - uv.x * 1.5);

  // NEXUS Light Mode: #F7FAF3 base with Emerald (#10B981) to Lime (#84CC16) streams
  vec3 lightCol = mix(vec3(0.925, 0.969, 0.890), vec3(0.969, 0.980, 0.953), wave * 0.6);
  lightCol = mix(lightCol, vec3(0.063, 0.725, 0.506), smoothstep(0.32, 0.86, wave) * 0.45);
  lightCol = mix(lightCol, vec3(0.518, 0.800, 0.086), smoothstep(0.56, 0.96, accent) * 0.42);

  // NEXUS Dark Mode: derived dark forest-lime tones (#0A140C -> #112014) with #10B981 & #84CC16 streams
  vec3 darkCol = mix(vec3(0.039, 0.078, 0.047), vec3(0.067, 0.125, 0.078), wave);
  darkCol = mix(darkCol, vec3(0.063, 0.550, 0.380), smoothstep(0.38, 0.85, wave) * 0.65);
  darkCol = mix(darkCol, vec3(0.518, 0.800, 0.086), smoothstep(0.65, 0.98, accent) * 0.40);

  vec3 col = mix(lightCol, darkCol, u_dark);
  gl_FragColor = vec4(col, 1.0);
}`;

export function SmokeShaderBackground({ theme, className }: SmokeShaderBackgroundProps) {
  const { resolvedTheme } = useTheme();
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);
  const activeTheme: ThemeMode = theme ?? (!mounted || resolvedTheme === "dark" ? "dark" : "light");
  const isDark = activeTheme === "dark";

  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const darkRef = useRef(isDark ? 1 : 0);
  const redrawRef = useRef<() => void>(() => {});

  useEffect(() => {
    const canvas = canvasRef.current;
    const gl = canvas?.getContext("webgl", { antialias: false, alpha: false, depth: false });
    if (!canvas || !gl) return; // Static theme background underneath stands in.

    const compileShader = (type: number, src: string) => {
      const s = gl.createShader(type);
      if (!s) return null;
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) {
        gl.deleteShader(s);
        return null;
      }
      return s;
    };

    const vs = compileShader(gl.VERTEX_SHADER, VERT);
    const fs = compileShader(gl.FRAGMENT_SHADER, FRAG);
    if (!vs || !fs) return;

    const program = gl.createProgram();
    if (!program) return;
    gl.attachShader(program, vs);
    gl.attachShader(program, fs);
    gl.linkProgram(program);
    if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
      gl.deleteProgram(program);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
      return;
    }
    gl.useProgram(program);

    const buffer = gl.createBuffer();
    gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
    gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
    gl.enableVertexAttribArray(0);
    gl.vertexAttribPointer(0, 2, gl.FLOAT, false, 0, 0);

    const uRes = gl.getUniformLocation(program, "u_resolution");
    const uTime = gl.getUniformLocation(program, "u_time");
    const uDark = gl.getUniformLocation(program, "u_dark");

    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)");
    const start = performance.now();
    let shade = darkRef.current;
    let time = 10;
    let raf = 0;
    let last = 0;

    const draw = () => {
      gl.uniform2f(uRes, canvas.width, canvas.height);
      gl.uniform1f(uTime, time);
      gl.uniform1f(uDark, shade);
      gl.drawArrays(gl.TRIANGLES, 0, 3);
    };

    const loop = (now: number) => {
      raf = requestAnimationFrame(loop);
      if (now - last < 1000 / 30 - 2) return;
      const dt = Math.min((now - last) / 1000, 0.1);
      last = now;
      time = 10 + (now - start) / 1000;
      shade += (darkRef.current - shade) * Math.min(1, dt * 3.5);
      draw();
    };

    const play = () => {
      cancelAnimationFrame(raf);
      if (reduce.matches) draw();
      else raf = requestAnimationFrame(loop);
    };

    redrawRef.current = () => {
      if (!reduce.matches) return;
      shade = darkRef.current;
      draw();
    };

    const ro = new ResizeObserver(() => {
      const s = Math.min(window.devicePixelRatio || 1, 2) * RENDER_SCALE;
      canvas.width = Math.max(1, Math.round(canvas.clientWidth * s));
      canvas.height = Math.max(1, Math.round(canvas.clientHeight * s));
      gl.viewport(0, 0, canvas.width, canvas.height);
      draw();
    });

    ro.observe(canvas);
    reduce.addEventListener("change", play);
    play();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      reduce.removeEventListener("change", play);
      gl.deleteBuffer(buffer);
      gl.deleteProgram(program);
      gl.deleteShader(vs);
      gl.deleteShader(fs);
    };
  }, []);

  useEffect(() => {
    darkRef.current = isDark ? 1 : 0;
    redrawRef.current();
  }, [isDark]);

  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden transition-colors duration-700",
        isDark ? "bg-[#0A140C]" : "bg-[#F7FAF3]",
        className,
      )}
    >
      {/* Static Theme Fallback (when WebGL is unavailable) */}
      <div
        className="absolute inset-0"
        style={{
          background: isDark
            ? "radial-gradient(ellipse 75% 55% at 50% 18%, rgba(132, 204, 22, 0.14) 0%, #112014 45%, #0A140C 100%)"
            : "radial-gradient(ellipse 75% 55% at 50% 18%, rgba(132, 204, 22, 0.16) 0%, #F7FAF3 55%, #FFFFFF 100%)",
        }}
      />

      <canvas ref={canvasRef} className="absolute inset-0 size-full" />

      {/* Subtle Bottom Fade for Readability & Transition */}
      <div
        className="absolute inset-0"
        style={{
          background: isDark
            ? "linear-gradient(to bottom, transparent 0%, rgba(10, 20, 12, 0.25) 60%, rgba(10, 20, 12, 0.85) 100%)"
            : "linear-gradient(to bottom, transparent 0%, rgba(255, 255, 255, 0.08) 70%, rgba(255, 255, 255, 0.55) 100%)",
        }}
      />
    </div>
  );
}

