import type { ReactNode } from "react";
import { AuthBackground } from "@/components/effects/auth-background";
import { ThemeToggle } from "@/components/shared/theme-toggle";

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="relative flex min-h-svh flex-col items-center justify-center p-6 md:p-10">
      <AuthBackground />
      <div className="fixed top-4 right-4 z-30 rounded-full border border-border/80 bg-card/85 p-1 shadow-sm backdrop-blur-md dark:border-[#223D27] dark:bg-[#112014]/85">
        <ThemeToggle />
      </div>
      <div className="relative z-10 w-full max-w-sm md:max-w-4xl">{children}</div>
    </div>
  );
}
