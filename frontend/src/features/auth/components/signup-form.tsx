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
import {
  evaluatePassword,
  PasswordStrengthMeter,
} from "@/features/auth/components/password-strength-meter";
import { ApiError } from "@/lib/api";
import { MockApiError } from "@/lib/mock-api";
import { cn } from "@/lib/utils";

export function SignupForm({ className }: { className?: string }) {
  const { sendRegistrationOtp, verifyRegistrationOtp, user, authProvider, onboardingCompleted, isAuthenticated, isLoading } = useAuth();
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [otpModalOpen, setOtpModalOpen] = useState(false);
  const [otpCode, setOtpCode] = useState("");
  const [otpLoading, setOtpLoading] = useState(false);
  const [otpError, setOtpError] = useState<string | null>(null);
  const [resendCooldown, setResendCooldown] = useState(0);

  const passwordEvaluation = evaluatePassword(password, confirmPassword);
  const canSubmit =
    Boolean(fullName.trim()) &&
    Boolean(companyName.trim()) &&
    Boolean(email.trim()) &&
    passwordEvaluation.isValid;

  useEffect(() => {
    if (isLoading || !isAuthenticated || !user) return;
    if (authProvider !== "mock" && !onboardingCompleted) {
      router.replace(CUSTOMER_ROUTES.onboarding);
      return;
    }
    router.replace(getDefaultRouteForRole(user.role));
  }, [isLoading, isAuthenticated, user, authProvider, onboardingCompleted, router]);

  useEffect(() => {
    if (resendCooldown <= 0) return;
    const timer = window.setTimeout(() => setResendCooldown((prev) => prev - 1), 1000);
    return () => window.clearTimeout(timer);
  }, [resendCooldown]);

  async function handleSubmit(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError(null);

    if (!passwordEvaluation.isValid) {
      setError("Please satisfy all required password criteria before creating your account.");
      return;
    }

    setLoading(true);
    try {
      await sendRegistrationOtp(email);
      setOtpCode("");
      setOtpError(null);
      setResendCooldown(30);
      setOtpModalOpen(true);
    } catch (err) {
      if (err instanceof ApiError || err instanceof MockApiError) {
        setError(err.message);
      } else {
        setError("Could not send verification code.");
      }
    } finally {
      setLoading(false);
    }
  }

  async function handleVerifyOtp(e: FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setOtpError(null);
    if (otpCode.trim().length < 4) {
      setOtpError("Please enter the verification code sent to your email.");
      return;
    }
    setOtpLoading(true);
    try {
      await verifyRegistrationOtp({
        fullName,
        companyName,
        email,
        password,
        otp: otpCode.trim(),
      });
      setOtpModalOpen(false);
      router.replace(CUSTOMER_ROUTES.onboarding);
    } catch (err) {
      if (err instanceof ApiError || err instanceof MockApiError) {
        setOtpError(err.message);
      } else {
        setOtpError("Invalid or expired verification code.");
      }
    } finally {
      setOtpLoading(false);
    }
  }

  async function handleResendOtp() {
    if (resendCooldown > 0) return;
    setOtpError(null);
    try {
      await sendRegistrationOtp(email);
      setResendCooldown(30);
    } catch (err) {
      setOtpError(err instanceof ApiError ? err.message : "Could not resend code.");
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
                <PasswordStrengthMeter password={password} confirmPassword={confirmPassword} />
              </div>

              {error && (
                <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
                  {error}
                </p>
              )}

              <Button
                type="submit"
                disabled={loading || !canSubmit}
                className="h-10 w-full rounded-lg bg-gradient-to-r from-[#10B981] to-[#84CC16] text-sm font-bold text-[#0A140C] transition-opacity hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {loading ? "Creating workspace..." : "Create Account"}
              </Button>

              <div className="relative flex items-center py-0.5">
                <div className="grow border-t border-border dark:border-[#223D27]" />
                <span className="mx-3 shrink text-[11px] font-medium text-muted-foreground uppercase">
                  Or sign up with
                </span>
                <div className="grow border-t border-border dark:border-[#223D27]" />
              </div>

              <div className="grid grid-cols-3 gap-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    window.location.href = "/api/v1/auth/oauth/google";
                  }}
                >
                  Google
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    window.location.href = "/api/v1/auth/oauth/linkedin";
                  }}
                >
                  LinkedIn
                </Button>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => {
                    window.location.href = "/api/v1/auth/oauth/microsoft";
                  }}
                >
                  Microsoft
                </Button>
              </div>

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
        By clicking continue, you agree to our <Link href="/landing-page#footer">Terms of Service</Link> and{" "}
        <Link href="/landing-page#footer">Privacy Policy</Link>.
      </div>

      {otpModalOpen && (
        <div
          role="dialog"
          aria-modal="true"
          aria-labelledby="otp-modal-title"
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/65 p-4 backdrop-blur-sm"
        >
          <Card className="w-full max-w-md rounded-2xl border-border/80 bg-card text-card-foreground shadow-2xl dark:border-[#223D27] dark:bg-[#112014] dark:text-lime-50">
            <CardContent className="p-6">
              <form onSubmit={handleVerifyOtp} className="space-y-4">
                <div className="space-y-1 text-center">
                  <h2 id="otp-modal-title" className="text-xl font-bold text-foreground dark:text-white">
                    Verify your email
                  </h2>
                  <p className="text-xs text-muted-foreground dark:text-lime-200/70">
                    Enter the 6-digit verification code sent to{" "}
                    <span className="font-semibold text-foreground dark:text-lime-200">{email}</span>
                  </p>
                </div>

                <div className="grid gap-1.5">
                  <Label htmlFor="signup-otp" className="text-foreground dark:text-lime-100">
                    Verification code
                  </Label>
                  <Input
                    id="signup-otp"
                    type="text"
                    inputMode="numeric"
                    autoComplete="one-time-code"
                    placeholder="123456"
                    maxLength={12}
                    required
                    autoFocus
                    value={otpCode}
                    onChange={(e) => setOtpCode(e.target.value)}
                    className="h-11 rounded-lg border-input bg-surface/70 text-center font-mono text-lg tracking-[0.35em] text-foreground placeholder:tracking-normal dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white"
                  />
                </div>

                {otpError && (
                  <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
                    {otpError}
                  </p>
                )}

                <Button
                  type="submit"
                  disabled={otpLoading}
                  className="h-10 w-full rounded-lg bg-gradient-to-r from-[#10B981] to-[#84CC16] text-sm font-bold text-[#0A140C] transition-opacity hover:opacity-90"
                >
                  {otpLoading ? "Verifying & creating workspace..." : "Verify & Create Account"}
                </Button>

                <div className="flex items-center justify-between text-xs">
                  <button
                    type="button"
                    disabled={resendCooldown > 0}
                    onClick={handleResendOtp}
                    className="font-medium text-primary hover:underline disabled:opacity-50 dark:text-lime-300"
                  >
                    {resendCooldown > 0 ? `Resend code in ${resendCooldown}s` : "Resend code"}
                  </button>
                  <button
                    type="button"
                    onClick={() => setOtpModalOpen(false)}
                    className="text-muted-foreground hover:text-foreground dark:hover:text-white"
                  >
                    Cancel
                  </button>
                </div>
              </form>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}
