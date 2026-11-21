import { SecuritySettingsPanel } from "@/features/auth/components/security-settings-panel";

export default function AdminSecurityPage() {
  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-bold tracking-tight text-foreground">Admin Security</h1>
        <p className="text-sm text-muted-foreground">
          Configure 2FA, biometric passkeys, and password recovery for your platform admin account.
        </p>
      </div>
      <SecuritySettingsPanel />
    </div>
  );
}
