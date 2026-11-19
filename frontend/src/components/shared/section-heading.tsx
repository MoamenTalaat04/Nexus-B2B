import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

interface SectionHeadingProps {
  eyebrow?: string;
  title: ReactNode;
  description?: string;
  align?: "left" | "center";
  className?: string;
}

export function SectionHeading({
  eyebrow,
  title,
  description,
  align = "center",
  className,
}: SectionHeadingProps) {
  return (
    <div
      className={cn(
        "space-y-3",
        align === "center" ? "mx-auto max-w-2xl text-center" : "max-w-xl text-left",
        className,
      )}
    >
      {eyebrow && (
        <Badge
          variant="secondary"
          className="border border-primary/20 bg-primary-light/80 px-3 py-1 text-[11px] font-bold tracking-wider text-emerald-dark uppercase dark:bg-surface-secondary dark:text-primary"
        >
          {eyebrow}
        </Badge>
      )}
      <h2 className="text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.15] font-bold tracking-tight text-foreground">
        {title}
      </h2>
      {description && <p className="text-base leading-relaxed text-muted-foreground md:text-lg">{description}</p>}
    </div>
  );
}

