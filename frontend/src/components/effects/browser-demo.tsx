"use client";

import { Play } from "lucide-react";
import { Safari } from "@/components/ui/safari";

interface BrowserDemoProps {
  videoSrc?: string;
  imageSrc?: string;
  url?: string;
}

export function BrowserDemo({ videoSrc, imageSrc, url = "app.nexus.ai" }: BrowserDemoProps) {
  if (videoSrc || imageSrc) {
    return (
      <div className="w-full overflow-hidden rounded-2xl border border-emerald-400/20 shadow-2xl shadow-emerald-950/60">
        <Safari url={url} videoSrc={videoSrc} imageSrc={imageSrc} className="w-full" />
      </div>
    );
  }

  return (
    <div className="relative w-full overflow-hidden rounded-2xl border border-border/80 bg-card shadow-2xl shadow-emerald-950/20 dark:border-emerald-400/20 dark:bg-[#04140E] dark:shadow-black/70">
      {/* Magic UI Safari Browser Frame */}
      <Safari url={url} mode="simple" className="pointer-events-none relative z-10 w-full" />

      {/* z-20 Video Container below Safari toolbar (top-[7%]) */}
      <div className="absolute inset-x-0 top-[6.9%] bottom-0 z-20 flex flex-col items-center justify-center rounded-b-2xl bg-gradient-to-b from-[#061D15] to-[#020E09] p-6 text-center">
        <div className="flex size-16 items-center justify-center rounded-full border border-emerald-400/35 bg-emerald-500/15 text-emerald-300 shadow-lg shadow-emerald-500/15 backdrop-blur-xs">
          <Play className="ml-0.5 size-7 fill-current" />
        </div>
        <p className="mt-4 text-sm font-semibold text-emerald-50 sm:text-base">Product Demo Video</p>
        <p className="mt-1 text-xs text-emerald-200/65">
          Video container ready — pass <code className="text-emerald-300">videoSrc</code> to play demo
        </p>
      </div>
    </div>
  );
}
