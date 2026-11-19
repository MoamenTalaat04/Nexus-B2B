import Link from "next/link";
import { cn } from "@/lib/utils";

interface LogoProps {
  className?: string;
  inverted?: boolean;
  compact?: boolean;
}

export function Logo({ className, inverted = false, compact = false }: LogoProps) {
  return (
    <Link href="/" className={cn("inline-flex items-center gap-2.5 font-bold tracking-tight", className)}>
      <span
        className={cn(
          "flex size-8 shrink-0 items-center justify-center rounded-lg shadow-xs",
          inverted ? "bg-emerald-400 text-emerald-deep" : "bg-primary text-primary-foreground",
        )}
      >
        <svg viewBox="0 0 24 24" className="size-4.5 fill-none stroke-current" strokeWidth="2.4">
          <path d="M5 19V5l14 14V5" strokeLinecap="round" strokeLinejoin="round" />
        </svg>
      </span>
      {!compact && (
        <span className={cn("text-lg font-extrabold tracking-tight", inverted ? "text-white" : "text-foreground")}>
          NEXUS
        </span>
      )}
    </Link>
  );
}

