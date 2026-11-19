"use client";

import dynamic from "next/dynamic";
import { useTheme } from "next-themes";
import { useEffect, useState, useSyncExternalStore } from "react";
import { cn } from "@/lib/utils";

const Shader = dynamic(() => import("shaders/react").then((mod) => mod.Shader), {
  ssr: false,
});

const Swirl = dynamic(() => import("shaders/react").then((mod) => mod.Swirl), {
  ssr: false,
});

const ChromaFlow = dynamic(() => import("shaders/react").then((mod) => mod.ChromaFlow), {
  ssr: false,
});

const FlutedGlass = dynamic(() => import("shaders/react").then((mod) => mod.FlutedGlass), {
  ssr: false,
});

const emptySubscribe = () => () => {};

interface HeroShaderBackgroundProps {
  className?: string;
}

export function HeroShaderBackground({ className }: HeroShaderBackgroundProps) {
  const { resolvedTheme } = useTheme();
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);
  const [gpuUnavailable, setGpuUnavailable] = useState(false);
  const [reduceMotion, setReduceMotion] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;

    const motionQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
    const sync = () => setReduceMotion(motionQuery.matches);

    queueMicrotask(sync);
    motionQuery.addEventListener("change", sync);
    return () => motionQuery.removeEventListener("change", sync);
  }, []);

  const isDark = !mounted || resolvedTheme === "dark";
  const shouldRenderShader = mounted && !gpuUnavailable && !reduceMotion;

  return (
    <div
      aria-hidden="true"
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden transition-colors duration-300",
        isDark ? "bg-[#041C15]" : "bg-[#F7FBF8]",
        className,
      )}
    >
      {/* Static Theme Base & WebGPU/Reduced-Motion Fallback */}
      <div
        className="absolute inset-0"
        style={{
          background: isDark
            ? "radial-gradient(ellipse 75% 52% at 50% 10%, rgba(0, 155, 114, 0.22) 0%, rgba(8, 42, 32, 0.55) 45%, #041C15 100%)"
            : "radial-gradient(ellipse 75% 50% at 50% 8%, rgba(85, 221, 176, 0.20) 0%, rgba(247, 251, 248, 0.88) 55%, #FFFFFF 100%)",
        }}
      />

      {/* Official Shaders React GlassBackground (Swirl + ChromaFlow + FlutedGlass) */}
      {shouldRenderShader && (
        <Shader
          key={isDark ? "hero-glass-dark" : "hero-glass-light"}
          colorSpace="srgb"
          toneMapping="aces"
          onUnavailable={() => setGpuUnavailable(true)}
          className="absolute inset-0 h-full w-full"
        >
          {isDark ? (
            <>
              <Swirl colorA="#041C15" colorB="#082A20" detail={1.5} speed={0.4} />
              <ChromaFlow
                baseColor="#041C15"
                downColor="#009B72"
                leftColor="#55DDB0"
                radius={4}
                rightColor="#00C78B"
                upColor="#D9FF83"
                intensity={0.75}
              />
              <FlutedGlass
                aberration={0}
                angle={30}
                frequency={8}
                lightAngle={-90}
                refraction={4}
                shape="rounded"
                softness={1}
              />
            </>
          ) : (
            <>
              <Swirl colorA="#FFFFFF" colorB="#F0FAF4" detail={1.5} speed={0.35} />
              <ChromaFlow
                baseColor="#FFFFFF"
                downColor="#10B981"
                leftColor="#55DDB0"
                radius={4}
                rightColor="#00C78B"
                upColor="#A7F3D0"
                intensity={0.55}
              />
              <FlutedGlass
                aberration={0}
                angle={30}
                frequency={8}
                lightAngle={-90}
                refraction={4}
                shape="rounded"
                softness={1}
              />
            </>
          )}
        </Shader>
      )}

      {/* Subtle Contrast Scrim behind Browser Mockup & Smooth Bottom Transition */}
      <div
        className="absolute inset-0"
        style={{
          background: isDark
            ? "linear-gradient(to bottom, rgba(4, 28, 21, 0.14) 0%, rgba(4, 28, 21, 0.38) 54%, rgba(4, 28, 21, 0.92) 100%)"
            : "linear-gradient(to bottom, rgba(247, 251, 248, 0.10) 0%, rgba(255, 255, 255, 0.42) 58%, rgba(255, 255, 255, 0.90) 100%)",
        }}
      />
    </div>
  );
}
