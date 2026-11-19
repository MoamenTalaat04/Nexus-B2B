"use client";

import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";
import { AnimatedThemeToggler } from "@/components/ui/animated-theme-toggler";
import { cn } from "@/lib/utils";

const emptySubscribe = () => () => {};

export function ThemeToggle({ className }: { className?: string }) {
  const { resolvedTheme, setTheme } = useTheme();
  const mounted = useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  );

  if (!mounted) {
    return <div aria-hidden="true" className={cn("size-8", className)} />;
  }

  const current = resolvedTheme === "dark" ? "dark" : "light";

  return (
    <AnimatedThemeToggler
      theme={current}
      onThemeChange={(next) => setTheme(next)}
      aria-label="Toggle color theme"
      className={cn(
        "inline-flex size-8 cursor-pointer items-center justify-center text-foreground/80 transition-colors hover:text-foreground focus-visible:outline-none",
        className,
      )}
    />
  );
}
