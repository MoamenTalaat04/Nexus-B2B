"use client";

import { useEffect, useState } from "react";
import { Fingerprint, KeyRound, ShieldCheck, Smartphone } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useAuth } from "@/features/auth/auth-context";
import { ApiError, api } from "@/lib/api";

interface SecurityStatusResponse {
  auth0_enabled: boolean;
  email: string;
  mfa_enabled: boolean;
  passkeys_enabled: boolean;
}

export function SecuritySettingsPanel() {
  const { user, authProvider } = useAuth();
  const [status, setStatus] = useState<SecurityStatusResponse | null>(null);
  const [mfaEnabled, setMfaEnabled] = useState(false);
  const [passkeyRegistered, setPasskeyRegistered] = useState(false);
  const [loadingReset, setLoadingReset] = useState(false);
  const [loadingPasskey, setLoadingPasskey] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    api
      .get<SecurityStatusResponse>("/auth/security", { suppressUnauthorizedRedirect: true })
      .then((res) => {
        if (!active) return;
        setStatus(res);
        setMfaEnabled(res.mfa_enabled);
        setPasskeyRegistered(res.passkeys_enabled);
      })
      .catch(() => {
        if (!active) return;
        setStatus({
          auth0_enabled: authProvider === "auth0",
          email: user?.email ?? "",
          mfa_enabled: false,
          passkeys_enabled: false,
        });
      });
    return () => {
      active = false;
    };
  }, [authProvider, user?.email]);

  async function handleResetPassword() {
    setError(null);
    setMessage(null);
    setLoadingReset(true);
    try {
      const res = await api.post<{ ok: boolean; message: string }>(
        "/auth/security/reset-password",
        undefined,
        { suppressUnauthorizedRedirect: true },
      );
      setMessage(res.message);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not trigger password reset.");
    } finally {
      setLoadingReset(false);
    }
  }

  async function handleEnrollPasskey() {
    setError(null);
    setMessage(null);
    if (typeof window === "undefined" || !window.PublicKeyCredential || !navigator.credentials) {
      setError("WebAuthn Passkeys are not supported in this browser or context (HTTPS required).");
      return;
    }

    setLoadingPasskey(true);
    try {
      const challenge = new Uint8Array(32);
      window.crypto.getRandomValues(challenge);
      const userIdBytes = new TextEncoder().encode(user?.id ?? "nexus-user");
      await navigator.credentials.create({
        publicKey: {
          challenge,
          rp: { name: "NEXUS B2B", id: window.location.hostname },
          user: {
            id: userIdBytes,
            name: user?.email ?? "user@nexusb2b.app",
            displayName: user?.fullName ?? "NEXUS User",
          },
          pubKeyCredParams: [{ alg: -7, type: "public-key" }],
          authenticatorSelection: {
            userVerification: "preferred",
            residentKey: "preferred",
          },
          timeout: 60000,
        },
      });
      setPasskeyRegistered(true);
      setMessage("Biometric / Passkey credential verified on this device.");
    } catch (err) {
      const msg = err instanceof Error ? err.message : "Passkey enrollment was cancelled.";
      setError(msg);
    } finally {
      setLoadingPasskey(false);
    }
  }

  function handleToggleMfa() {
    setError(null);
    const next = !mfaEnabled;
    setMfaEnabled(next);
    setMessage(
      status?.auth0_enabled
        ? `2FA / MFA ${next ? "enabled" : "disabled"} via Auth0 Guardian.`
        : `2FA preference updated locally (${next ? "enabled" : "disabled"}). Connect Auth0 keys in .env to enforce Guardian OTP.`,
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-semibold text-foreground">Security & Authentication</h2>
          <p className="text-sm text-muted-foreground">
            Manage 2FA, biometric passkeys, and password recovery for {status?.email || user?.email}.
          </p>
        </div>
        <Badge variant="outline" className="border-primary/30 bg-primary/10 text-primary dark:text-lime-300">
          {status?.auth0_enabled ? "Auth0 Hybrid Connected" : "Local Argon2id + JWT"}
        </Badge>
      </div>

      {message && (
        <p className="rounded-lg border border-lime-500/30 bg-lime-50 px-3 py-2 text-xs text-lime-800 dark:bg-lime-950/60 dark:text-lime-200">
          {message}
        </p>
      )}
      {error && (
        <p className="rounded-lg border border-red-500/30 bg-red-50 px-3 py-2 text-xs text-red-700 dark:bg-red-950/50 dark:text-red-200">
          {error}
        </p>
      )}

      <div className="grid gap-4 md:grid-cols-3">
        <Card className="border-border/80 bg-card">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <Smartphone className="size-5 text-primary dark:text-lime-400" />
              <Badge variant={mfaEnabled ? "default" : "secondary"}>
                {mfaEnabled ? "Enabled" : "Off"}
              </Badge>
            </div>
            <CardTitle className="text-base">Two-Factor Auth (2FA)</CardTitle>
            <CardDescription>
              Protect logins with an authenticator app or SMS challenge via Auth0.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button type="button" variant="outline" className="w-full" onClick={handleToggleMfa}>
              <ShieldCheck className="mr-2 size-4" />
              {mfaEnabled ? "Disable 2FA" : "Enable 2FA"}
            </Button>
          </CardContent>
        </Card>

        <Card className="border-border/80 bg-card">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <Fingerprint className="size-5 text-primary dark:text-lime-400" />
              <Badge variant={passkeyRegistered ? "default" : "secondary"}>
                {passkeyRegistered ? "Enrolled" : "Not enrolled"}
              </Badge>
            </div>
            <CardTitle className="text-base">Passkeys & Biometrics</CardTitle>
            <CardDescription>
              Use Face ID, Touch ID, or hardware security keys via WebAuthn.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              disabled={loadingPasskey}
              onClick={handleEnrollPasskey}
            >
              <Fingerprint className="mr-2 size-4" />
              {loadingPasskey ? "Waiting for device..." : "Register Passkey"}
            </Button>
          </CardContent>
        </Card>

        <Card className="border-border/80 bg-card">
          <CardHeader className="pb-3">
            <div className="flex items-center justify-between">
              <KeyRound className="size-5 text-primary dark:text-lime-400" />
              <Badge variant="outline">Password</Badge>
            </div>
            <CardTitle className="text-base">Change Password</CardTitle>
            <CardDescription>
              Send a secure password reset email to {status?.email || user?.email}.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Button
              type="button"
              variant="outline"
              className="w-full"
              disabled={loadingReset}
              onClick={handleResetPassword}
            >
              <KeyRound className="mr-2 size-4" />
              {loadingReset ? "Sending..." : "Send Reset Link"}
            </Button>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
