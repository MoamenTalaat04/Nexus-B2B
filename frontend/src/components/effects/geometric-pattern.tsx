import { GridPattern } from "@/components/ui/grid-pattern";
import { cn } from "@/lib/utils";

interface GeometricPatternProps {
  variant?: "dots-corners" | "grid-fade" | "curved-lines";
  className?: string;
}

export function GeometricPattern({ variant = "grid-fade", className }: GeometricPatternProps) {
  if (variant === "dots-corners") {
    return (
      <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)} aria-hidden="true">
        <svg className="absolute -top-6 -left-6 h-48 w-48 text-primary/15" viewBox="0 0 120 120" fill="none">
          <defs>
            <pattern id="nexus-dots-tl" x="0" y="0" width="12" height="12" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1.3" fill="currentColor" />
            </pattern>
          </defs>
          <rect width="120" height="120" fill="url(#nexus-dots-tl)" />
        </svg>
        <svg className="absolute -right-6 -bottom-6 h-48 w-48 text-primary/15" viewBox="0 0 120 120" fill="none">
          <defs>
            <pattern id="nexus-dots-br" x="0" y="0" width="12" height="12" patternUnits="userSpaceOnUse">
              <circle cx="2" cy="2" r="1.3" fill="currentColor" />
            </pattern>
          </defs>
          <rect width="120" height="120" fill="url(#nexus-dots-br)" />
        </svg>
      </div>
    );
  }

  if (variant === "curved-lines") {
    return (
      <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)} aria-hidden="true">
        <svg
          className="absolute inset-0 size-full text-primary/[0.08]"
          viewBox="0 0 1200 400"
          fill="none"
          preserveAspectRatio="none"
        >
          <path d="M-50 320 C 260 120, 560 360, 1250 100" stroke="currentColor" strokeWidth="1.5" />
          <path d="M-50 360 C 300 180, 620 400, 1250 160" stroke="currentColor" strokeWidth="1" strokeDasharray="6 6" />
        </svg>
      </div>
    );
  }

  return (
    <div className={cn("pointer-events-none absolute inset-0 overflow-hidden", className)} aria-hidden="true">
      <GridPattern
        width={36}
        height={36}
        className="fill-primary/[0.025] stroke-primary/[0.06] [mask-image:radial-gradient(ellipse_at_center,white,transparent_75%)]"
      />
    </div>
  );
}

