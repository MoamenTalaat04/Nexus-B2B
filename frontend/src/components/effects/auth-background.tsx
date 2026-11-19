"use client";

import { SmokeShaderBackground } from "@/components/ui/smoke-shader-background";
import { cn } from "@/lib/utils";

export function AuthBackground({ className }: { className?: string }) {
  return (
    <div className={cn("pointer-events-none fixed inset-0 overflow-hidden", className)} aria-hidden="true">
      <SmokeShaderBackground className="size-full" />
    </div>
  );
}
