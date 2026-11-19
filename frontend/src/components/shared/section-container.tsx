import type { ReactNode } from "react";
import { cn } from "@/lib/utils";

interface SectionContainerProps {
  id?: string;
  children: ReactNode;
  className?: string;
  innerClassName?: string;
}

export function SectionContainer({ id, children, className, innerClassName }: SectionContainerProps) {
  return (
    <section id={id} className={cn("relative overflow-hidden py-20 md:py-28", className)}>
      <div className={cn("relative z-10 mx-auto w-full max-w-7xl px-4 sm:px-6 lg:px-8", innerClassName)}>
        {children}
      </div>
    </section>
  );
}

