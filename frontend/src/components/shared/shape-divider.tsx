import { cn } from "@/lib/utils";

interface ShapeDividerProps {
  className?: string;
  variant?: "hero-wave" | "subtle-arc";
}

export function ShapeDivider({ className, variant = "hero-wave" }: ShapeDividerProps) {
  if (variant === "subtle-arc") {
    return (
      <div className={cn("pointer-events-none w-full overflow-hidden leading-none", className)} aria-hidden="true">
        <svg viewBox="0 0 1440 64" fill="none" preserveAspectRatio="none" className="block h-10 w-full md:h-14">
          <path
            d="M0 64V32C360 0 1080 0 1440 32V64H0Z"
            className="fill-background transition-colors duration-300"
          />
        </svg>
      </div>
    );
  }

  return (
    <div
      className={cn("pointer-events-none relative z-20 -mt-1 w-full overflow-hidden leading-none", className)}
      aria-hidden="true"
    >
      <svg viewBox="0 0 1440 96" fill="none" preserveAspectRatio="none" className="block h-12 w-full sm:h-16 md:h-24">
        <path
          d="M0 32C240 88 520 96 760 64C1020 29 1240 12 1440 48V96H0V32Z"
          className="fill-background transition-colors duration-300"
        />
        <path
          d="M0 24C240 80 520 88 760 56C1020 21 1240 4 1440 40"
          stroke="currentColor"
          strokeWidth="1.5"
          className="text-emerald-300/35 dark:text-emerald-400/20"
        />
      </svg>
    </div>
  );
}

