import * as React from "react";
import { cn } from "@/lib/utils";

export interface AutoDirTextProps extends React.HTMLAttributes<HTMLElement> {
  as?: "span" | "p" | "div" | "h1" | "h2" | "h3" | "h4";
  children: React.ReactNode;
}

/**
 * Renders user-authored or mixed Arabic/English text with `dir="auto"`
 * so the browser resolves bidirectional alignment per element.
 */
export function AutoDirText({
  as: Component = "span",
  className,
  children,
  ...props
}: AutoDirTextProps) {
  return (
    <Component dir="auto" className={cn(className)} {...props}>
      {children}
    </Component>
  );
}
