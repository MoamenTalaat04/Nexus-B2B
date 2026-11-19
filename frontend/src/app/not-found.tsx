import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Logo } from "@/components/shared/logo";
import { ThemeToggle } from "@/components/shared/theme-toggle";
import { AuroraText } from "@/components/ui/aurora-text";
import { Button } from "@/components/ui/button";
import { SmokeShaderBackground } from "@/components/ui/smoke-shader-background";

export default function NotFoundPage() {
  return (
    <div className="relative flex min-h-svh flex-col items-center justify-center overflow-hidden bg-background px-6 py-16 text-foreground">
      <SmokeShaderBackground />

      <div className="fixed top-4 right-4 z-30 rounded-full border border-border/80 bg-card/85 p-1 shadow-sm backdrop-blur-md dark:border-[#223D27] dark:bg-[#112014]/85">
        <ThemeToggle />
      </div>

      <div className="relative z-10 w-full max-w-lg rounded-3xl border border-border/80 bg-card/90 p-8 text-center shadow-2xl shadow-lime-950/10 backdrop-blur-xl sm:p-10 dark:border-[#223D27] dark:bg-[#112014]/90 dark:shadow-black/60">
        <div className="mb-6 flex justify-center">
          <Logo />
        </div>

        <p className="text-6xl font-extrabold tracking-tight sm:text-7xl">
          <AuroraText colors={["#079669", "#65A30D", "#84CC16", "#10B981"]} speed={1.2} className="font-extrabold">
            404
          </AuroraText>
        </p>

        <h1 className="mt-4 text-2xl font-bold tracking-tight text-foreground dark:text-white">
          Page not found
        </h1>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground dark:text-lime-200/75">
          The page you&apos;re looking for doesn&apos;t exist or may have been moved.
        </p>

        <div className="mt-8 flex flex-wrap items-center justify-center gap-3">
          <Button
            className="h-10 rounded-full bg-gradient-to-r from-[#10B981] to-[#84CC16] px-6 text-sm font-bold text-[#0A140C] transition-opacity hover:opacity-90"
            render={
              <Link href="/">
                <ArrowLeft className="mr-1.5 size-4" />
                Back to Home
              </Link>
            }
          />
          <Button
            variant="outline"
            className="h-10 rounded-full border-border bg-surface/70 px-6 text-sm font-semibold text-foreground hover:bg-surface-secondary dark:border-[#223D27] dark:bg-[#0A140C] dark:text-lime-100"
            render={<Link href="/login">Sign in</Link>}
          />
        </div>
      </div>
    </div>
  );
}

