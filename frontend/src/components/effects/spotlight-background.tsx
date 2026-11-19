"use client";

import dynamic from "next/dynamic";
import { GridPattern } from "@/components/ui/grid-pattern";
import { cn } from "@/lib/utils";

const Aurora = dynamic(() => import("@/components/Aurora"), { ssr: false });

interface SpotlightBackgroundProps {
  className?: string;
}

export function SpotlightBackground({ className }: SpotlightBackgroundProps) {
  return (
    <div
      className={cn(
        "pointer-events-none absolute inset-0 overflow-hidden bg-[#020E09]",
        className,
      )}
      aria-hidden="true"
    >
      {/* Zone 1: Bright Moving Glowing WebGL Emerald Aurora around top & outer edges */}
      <div className="animate-aurora-pulse absolute inset-0">
        <Aurora
          colorStops={["#00F5A0", "#34D399", "#10B981", "#059669", "#065F46"]}
          amplitude={1.15}
          blend={0.75}
          speed={0.55}
          height={1.05}
          glow={1.85}
          brightness={1.55}
          layers={3}
          direction="top"
          opacity={1}
        />
      </div>

      {/* Extra soft blurred emerald halo along the top & upper corners */}
      <div className="animate-aurora-pulse absolute -top-24 -left-24 h-[420px] w-[62%] rounded-full bg-emerald-400/25 blur-[110px]" />
      <div className="animate-aurora-pulse absolute -top-24 -right-24 h-[380px] w-[55%] rounded-full bg-emerald-500/20 blur-[110px]" />

      {/* Zone 2: Smoothly blurred deep dark emerald dome in the center & bottom */}
      <div
        className="absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 64% 62% at 50% 72%, #020E09 0%, rgba(2, 14, 9, 0.94) 44%, rgba(2, 14, 9, 0.55) 72%, rgba(2, 14, 9, 0.08) 100%)",
        }}
      />

      {/* Subtle Magic UI GridPattern texture */}
      <GridPattern
        width={48}
        height={48}
        x={-1}
        y={-1}
        className="fill-emerald-400/[0.02] stroke-emerald-300/[0.05] [mask-image:radial-gradient(ellipse_at_center,white,transparent_85%)]"
      />
    </div>
  );
}
