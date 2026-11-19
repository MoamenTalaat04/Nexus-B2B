"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState, type FormEvent } from "react";
import { Logo } from "@/components/shared/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AUTH_ROUTES, CUSTOMER_ROUTES, getDefaultRouteForRole } from "@/config/routes";
import { useAuth } from "@/features/auth/auth-context";
import { MockApiError } from "@/lib/mock-api";
import { cn } from "@/lib/utils";

export function SignupForm({ className }: { className?: string }) {
  const { registerCustomer, user, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isLoading || !isAuthenticated || !user) return;
    router.replace(getDefaultRouteForRole(user.role));
  }, [isLoading, isAuthenticated, user, router]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (password.length < 8) {
      setError("Password must be at least 8 characters long.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }

    setLoading(true);
    try {
      await registerCustomer({
        fullName,
        companyName,
        email,
        password,
      });
      router.replace(CUSTOMER_ROUTES.dashboard);
    } catch (err) {
      setError(err instanceof MockApiError ? err.message : "Could not create account.");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className={cn("flex flex-col gap-6", className)}>
      <Card className="overflow-hidden rounded-2xl border-border/80 bg-card/90 p-0 text-card-foreground shadow-2xl shadow-lime-950/10 backdrop-blur-xl dark:border-[#223D27] dark:bg-[#112014]/90 dark:text-lime-50 dark:shadow-black/60">
        <CardContent className="grid p-0 md:grid-cols-2">
          <form onSubmit={handleSubmit} className="p-6 md:p-8">
            <div className="flex flex-col gap-4">
              <div className="flex flex-col items-center gap-1.5 text-center">
                <h1 className="text-2xl font-bold tracking-tight text-foreground dark:text-white">
                  Create your workspace
                </h1>
                <p className="text-sm text-balance text-muted-foreground dark:text-lime-200/70">
                  Register a new customer account to get started
                </p>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                <div className="grid gap-1.5">
                  <Label htmlFor="signup-fullname" className="text-foreground dark:text-lime-100">
                    Full name
                  </Label>
                  <Input
                    id="signup-fullname"
                    type="text"
                    placeholder="Ahmed Hassan"
                    required
                    value={fullName}
                    onChange={(e) => setFullName(e.target.value)}
                    className="h-10 rounded-lg border-input bg-surface/70 text-foreground placeholder:text-muted-foreground/60 focus-visible:border-primary focus-visible:ring-primary/25 dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white dark:placeholder:text-lime-200/40 dark:focus-visible:border-lime-400 dark:focus-visible:ring-lime-400/30"
                  />
                </div>
                <div className="grid gap-1.5">
                  <Label htmlFor="signup-company" className="text-foreground dark:text-lime-100">
                    Company name
                  </Label>
                  <Input
                    id="signup-company"
                    type="text"
                    placeholder="Acme B2B"
                    required
                    value={companyName}
                    onChange={(e) => setCompanyName(e.target.value)}
                    className="h-10 rounded-lg border-input bg-surface/70 text-foreground placeholder:text-muted-foreground/60 focus-visible:border-primary focus-visible:ring-primary/25 dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white dark:placeholder:text-lime-200/40 dark:focus-visible:border-lime-400 dark:focus-visible:ring-lime-400/30"
                  />
                </div>
              </div>

              <div className="grid gap-1.5">
                <Label htmlFor="signup-email" className="text-foreground dark:text-lime-100">
                  Work email
                </Label>
                <Input
                  id="signup-email"
                  type="email"
                  placeholder="you@company.com"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-10 rounded-lg border-input bg-surface/70 text-foreground placeholder:text-muted-foreground/60 focus-visible:border-primary focus-visible:ring-primary/25 dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white dark:placeholder:text-lime-200/40 dark:focus-visible:border-lime-400 dark:focus-visible:ring-lime-400/30"
                />
              </div>

              <div className="grid gap-1.5">
                <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
                  <div className="grid gap-1.5">
                    <Label htmlFor="signup-password" className="text-foreground dark:text-lime-100">
                      Password
                    </Label>
                    <Input
                      id="signup-password"
                      type="password"
                      required
                      value={password}
                      onChange={(e) => setPassword(e.target.value)}
                      className="h-10 rounded-lg border-input bg-surface/70 text-foreground placeholder:text-muted-foreground/60 focus-visible:border-primary focus-visible:ring-primary/25 dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white dark:placeholder:text-lime-200/40 dark:focus-visible:border-lime-400 dark:focus-visible:ring-lime-400/30"
                    />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="confirm-password" className="text-foreground dark:text-lime-100">
                      Confirm Password
                    </Label>
                    <Input
                      id="confirm-password"
                      type="password"
                      required
                      value={confirmPassword}
                      onChange={(e) => setConfirmPassword(e.target.value)}
                      className="h-10 rounded-lg border-input bg-surface/70 text-foreground placeholder:text-muted-foreground/60 focus-visible:border-primary focus-visible:ring-primary/25 dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white dark:placeholder:text-lime-200/40 dark:focus-visible:border-lime-400 dark:focus-visible:ring-lime-400/30"
                    />
                  </div>
                </div>
                <p className="text-xs text-muted-foreground dark:text-lime-200/55">
                  Must be at least 8 characters long.
                </p>
              </div>

              {error && (
                <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
                  {error}
                </p>
              )}

              <Button
                type="submit"
                disabled={loading}
                className="h-10 w-full rounded-lg bg-gradient-to-r from-[#10B981] to-[#84CC16] text-sm font-bold text-[#0A140C] transition-opacity hover:opacity-90"
              >
                {loading ? "Creating workspace..." : "Create Account"}
              </Button>

              <div className="text-center text-xs text-muted-foreground dark:text-lime-200/75">
                Already have an account?{" "}
                <Link
                  href={AUTH_ROUTES.login}
                  className="font-semibold text-primary underline underline-offset-4 hover:text-primary-hover dark:text-lime-300 dark:hover:text-white"
                >
                  Sign in
                </Link>
              </div>
            </div>
          </form>

          <div className="relative hidden flex-col items-center justify-center overflow-hidden border-l border-border/70 bg-gradient-to-br from-[#F7FAF3] via-[#EDF6DF] to-[#ECF8D4] p-8 md:flex dark:border-[#223D27] dark:from-[#192E1D] dark:via-[#112014] dark:to-[#0A140C]">
            <div className="pointer-events-none absolute -top-20 -right-20 size-64 rounded-full bg-lime-400/20 blur-3xl dark:bg-lime-400/15" />
            <div className="pointer-events-none absolute -bottom-20 -left-20 size-64 rounded-full bg-emerald-400/15 blur-3xl dark:bg-emerald-500/10" />
            <div className="relative z-10 flex flex-col items-center text-center">
              <Logo className="scale-110" />
              <p className="mt-4 max-w-xs text-sm leading-relaxed text-muted-foreground dark:text-lime-100/75">
                Launch your AI-powered B2B lead discovery and outreach workflow in minutes.
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="px-6 text-center text-xs text-balance text-muted-foreground dark:text-lime-200/60 [&_a]:underline [&_a]:underline-offset-4 [&_a]:hover:text-foreground dark:[&_a]:hover:text-lime-200">
        By clicking continue, you agree to our <Link href="/#footer">Terms of Service</Link> and{" "}
        <Link href="/#footer">Privacy Policy</Link>.
      </div>
    </div>
  );
}
