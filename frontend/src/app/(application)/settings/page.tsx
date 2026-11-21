"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { CUSTOMER_ROUTES } from "@/config/routes";
import { SecuritySettingsPanel } from "@/features/auth/components/security-settings-panel";
import { CustomerBillingView } from "@/features/billing/components/customer-billing-view";
import { KnowledgeUploader } from "@/features/knowledge/components/knowledge-uploader";
import { AgentSettingsPanel } from "@/features/settings/components/agent-settings-panel";
import { BusinessSettingsPanel } from "@/features/settings/components/business-settings-panel";
import { ChannelsSettingsPanel } from "@/features/settings/components/channels-settings-panel";
import { api } from "@/lib/api";
import type { SettingsOut } from "@/lib/settings-types";
import { cn } from "@/lib/utils";

const SETTINGS_TABS = [
  { id: "business", label: "Business" },
  { id: "agent", label: "Agent" },
  { id: "knowledge", label: "Knowledge" },
  { id: "channels", label: "Channels" },
  { id: "billing", label: "Plan & Billing" },
  { id: "team", label: "Team" },
  { id: "security", label: "Security" },
] as const;

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<(typeof SETTINGS_TABS)[number]["id"]>("business");
  const [settings, setSettings] = useState<SettingsOut | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    api
      .get<SettingsOut>("/settings", { suppressUnauthorizedRedirect: true })
      .then((res) => {
        if (active) setSettings(res);
      })
      .catch(() => {})
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-xl font-bold tracking-tight text-foreground">Settings</h1>
        {settings && !settings.onboarding_completed && (
          <Link href={CUSTOMER_ROUTES.onboarding}>
            <Button size="sm" variant="outline">
              <Sparkles className="mr-1.5 size-4 text-primary dark:text-lime-400" />
              Launch Onboarding Wizard
            </Button>
          </Link>
        )}
      </div>

      <div role="tablist" aria-label="Settings sections" className="flex flex-wrap gap-2 border-b border-border pb-3">
        {SETTINGS_TABS.map((tab) => (
          <button
            key={tab.id}
            type="button"
            role="tab"
            aria-selected={activeTab === tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              "rounded-lg px-3.5 py-1.5 text-sm font-medium transition-colors",
              activeTab === tab.id
                ? "bg-primary/12 font-semibold text-primary dark:bg-lime-500/15 dark:text-lime-300"
                : "text-muted-foreground hover:bg-surface-secondary hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      <div role="tabpanel">
        {activeTab === "billing" ? (
          <CustomerBillingView />
        ) : activeTab === "security" ? (
          <SecuritySettingsPanel />
        ) : activeTab === "knowledge" ? (
          <KnowledgeUploader />
        ) : activeTab === "team" ? (
          <p className="text-sm text-muted-foreground">
            Workspace team invitations and member management are available for workspace owners.
          </p>
        ) : loading ? (
          <p className="text-sm text-muted-foreground">Loading workspace settings...</p>
        ) : !settings ? (
          <p className="text-sm text-muted-foreground">
            Sign in with a customer workspace account to view and edit these settings.
          </p>
        ) : activeTab === "business" ? (
          <BusinessSettingsPanel settings={settings} onUpdated={setSettings} />
        ) : activeTab === "agent" ? (
          <AgentSettingsPanel settings={settings} onUpdated={setSettings} />
        ) : (
          <ChannelsSettingsPanel settings={settings} onUpdated={setSettings} />
        )}
      </div>
    </div>
  );
}
