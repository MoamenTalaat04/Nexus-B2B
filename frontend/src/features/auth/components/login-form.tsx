"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState, type FormEvent } from "react";
import { Fingerprint } from "lucide-react";
import { Logo } from "@/components/shared/logo";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { AUTH_ROUTES, canAccessRoute, getDefaultRouteForRole } from "@/config/routes";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError, api } from "@/lib/api";
import { DEMO_CREDENTIALS, MockApiError } from "@/lib/mock-api";
import { cn } from "@/lib/utils";

const DEMO_ACCOUNTS = [
  { label: "Super Admin", ...DEMO_CREDENTIALS.superAdmin },
  { label: "Platform Admin", ...DEMO_CREDENTIALS.platformAdmin },
  { label: "Customer 1", ...DEMO_CREDENTIALS.customer1 },
  { label: "Customer 2", ...DEMO_CREDENTIALS.customer2 },
] as const;

function LoginFormInner({ className }: { className?: string }) {
  const { login, user, isAuthenticated, isLoading, resetDemoData } = useAuth();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [forgotMode, setForgotMode] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [info, setInfo] = useState<string | null>(null);

  useEffect(() => {
    if (isLoading || !isAuthenticated || !user) return;
    const nextPath = searchParams.get("next");
    const target =
      nextPath && canAccessRoute(user.role, nextPath) ? nextPath : getDefaultRouteForRole(user.role);
    router.replace(target);
  }, [isLoading, isAuthenticated, user, router, searchParams]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);
    setInfo(null);
    setLoading(true);
    try {
      if (forgotMode) {
        const res = await api.post<{ ok: boolean; message: string }>(
          "/auth/forgot-password",
          { email },
          { suppressUnauthorizedRedirect: true },
        );
        setInfo(res.message);
        setForgotMode(false);
        return;
      }
      const result = await login(email, password);
      const nextPath = searchParams.get("next");
      const target =
        nextPath && canAccessRoute(result.user.role, nextPath)
          ? nextPath
          : getDefaultRouteForRole(result.user.role);
      router.replace(target);
    } catch (err) {
      if (err instanceof ApiError || err instanceof MockApiError) {
        setError(err.message);
      } else {
        setError("Invalid email or password.");
      }
    } finally {
      setLoading(false);
    }
  }

  function handleOAuth(provider: "google" | "linkedin" | "microsoft") {
    window.location.href = `/api/v1/auth/oauth/${provider}`;
  }

  async function handlePasskeyLogin() {
    setError(null);
    setInfo(null);
    if (typeof window === "undefined" || !window.PublicKeyCredential || !navigator.credentials) {
      setError("Biometric / Passkey sign-in requires HTTPS and a compatible browser.");
      return;
    }
    try {
      const challenge = new Uint8Array(32);
      window.crypto.getRandomValues(challenge);
      await navigator.credentials.get({
        publicKey: {
          challenge,
          rpId: window.location.hostname,
          userVerification: "preferred",
          timeout: 60000,
        },
      });
      setInfo("Passkey verified. Complete Auth0 connection in .env to bind passkey sessions.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Passkey sign-in was cancelled.");
    }
  }

  async function handleResetDemo() {
    setError(null);
    await resetDemoData();
    setInfo("Mock database reset to initial seeded demo accounts.");
  }

  return (
    <div className={cn("flex flex-col gap-6", className)}>
      <Card className="overflow-hidden rounded-2xl border-border/80 bg-card/90 p-0 text-card-foreground shadow-2xl shadow-lime-950/10 backdrop-blur-xl dark:border-[#223D27] dark:bg-[#112014]/90 dark:text-lime-50 dark:shadow-black/60">
        <CardContent className="grid p-0 md:grid-cols-2">
          <form onSubmit={handleSubmit} className="p-6 md:p-8">
            <div className="flex flex-col gap-5">
              <div className="flex flex-col items-center gap-1.5 text-center">
                <h1 className="text-2xl font-bold tracking-tight text-foreground dark:text-white">Welcome back</h1>
                <p className="text-sm text-balance text-muted-foreground dark:text-lime-200/70">
                  Login to your NEXUS account
                </p>
              </div>

              <div className="grid gap-2">
                <Label htmlFor="email" className="text-foreground dark:text-lime-100">
                  Email
                </Label>
                <Input
                  id="email"
                  type="email"
                  placeholder="m@example.com"
                  required
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  className="h-10 rounded-lg border-input bg-surface/70 text-foreground placeholder:text-muted-foreground/60 focus-visible:border-primary focus-visible:ring-primary/25 dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white dark:placeholder:text-lime-200/40 dark:focus-visible:border-lime-400 dark:focus-visible:ring-lime-400/30"
                />
              </div>

              {!forgotMode && (
                <div className="grid gap-2">
                  <div className="flex items-center justify-between">
                    <Label htmlFor="password" className="text-foreground dark:text-lime-100">
                      Password
                    </Label>
                    <button
                      type="button"
                      onClick={() => {
                        setForgotMode(true);
                        setError(null);
                        setInfo(null);
                      }}
                      className="text-xs font-medium text-primary hover:underline dark:text-lime-300"
                    >
                      Forgot password?
                    </button>
                  </div>
                  <Input
                    id="password"
                    type="password"
                    required
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    className="h-10 rounded-lg border-input bg-surface/70 text-foreground placeholder:text-muted-foreground/60 focus-visible:border-primary focus-visible:ring-primary/25 dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white dark:placeholder:text-lime-200/40 dark:focus-visible:border-lime-400 dark:focus-visible:ring-lime-400/30"
                  />
                </div>
              )}

              {error && (
                <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
                  {error}
                </p>
              )}
              {info && (
                <p className="rounded-lg border border-lime-500/30 bg-lime-50 px-3 py-2 text-xs text-lime-800 dark:bg-lime-950/60 dark:text-lime-200">
                  {info}
                </p>
              )}

              <Button
                type="submit"
                disabled={loading}
                className="h-10 w-full rounded-lg bg-gradient-to-r from-[#10B981] to-[#84CC16] text-sm font-bold text-[#0A140C] transition-opacity hover:opacity-90"
              >
                {loading
                  ? forgotMode
                    ? "Sending reset link..."
                    : "Signing in..."
                  : forgotMode
                    ? "Send password reset link"
                    : "Login"}
              </Button>

              {forgotMode && (
                <button
                  type="button"
                  onClick={() => {
                    setForgotMode(false);
                    setError(null);
                  }}
                  className="text-center text-xs font-medium text-primary hover:underline dark:text-lime-300"
                >
                  Back to password sign-in
                </button>
              )}

              <div className="relative flex items-center py-1">
                <div className="grow border-t border-border dark:border-[#223D27]" />
                <span className="mx-3 shrink text-[11px] font-medium text-muted-foreground uppercase">
                  Or continue with
                </span>
                <div className="grow border-t border-border dark:border-[#223D27]" />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <Button type="button" variant="outline" size="sm" onClick={() => handleOAuth("google")}>
                  Google
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => handleOAuth("linkedin")}>
                  LinkedIn
                </Button>
                <Button type="button" variant="outline" size="sm" onClick={() => handleOAuth("microsoft")}>
                  Microsoft
                </Button>
              </div>

              <Button type="button" variant="outline" size="sm" className="w-full" onClick={handlePasskeyLogin}>
                <Fingerprint className="mr-2 size-4 text-primary dark:text-lime-400" />
                Sign in with Passkey / Biometrics
              </Button>

              {/* Development Demo Account Quick-Fill */}
              <div className="rounded-xl border border-border/80 bg-surface/60 p-3 dark:border-[#223D27] dark:bg-[#0A140C]/80">
                <div className="mb-2 flex items-center justify-between">
                  <span className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                    Demo Accounts (Dev)
                  </span>
                  <button
                    type="button"
                    onClick={handleResetDemo}
                    className="text-[11px] font-medium text-primary hover:underline dark:text-lime-300"
                  >
                    Reset mock DB
                  </button>
                </div>
                <div className="grid grid-cols-2 gap-1.5">
                  {DEMO_ACCOUNTS.map((acc) => (
                    <button
                      key={acc.email}
                      type="button"
                      onClick={() => {
                        setEmail(acc.email);
                        setPassword(acc.password);
                        setError(null);
                      }}
                      className="rounded-md border border-border bg-card px-2 py-1.5 text-left text-[11px] font-medium text-foreground transition-colors hover:border-primary/50 hover:bg-surface-secondary dark:border-[#223D27] dark:bg-[#112014] dark:text-lime-100 dark:hover:border-lime-400/50"
                    >
                      {acc.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="text-center text-xs text-muted-foreground dark:text-lime-200/75">
                Don&apos;t have an account?{" "}
                <Link
                  href={AUTH_ROUTES.register}
                  className="font-semibold text-primary underline underline-offset-4 hover:text-primary-hover dark:text-lime-300 dark:hover:text-white"
                >
                  Create workspace
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
                Intelligence that connects business. Discover, qualify, and engage B2B prospects in one platform.
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

export function LoginForm({ className }: { className?: string }) {
  return (
    <Suspense fallback={null}>
      <LoginFormInner className={className} />
    </Suspense>
  );
}
