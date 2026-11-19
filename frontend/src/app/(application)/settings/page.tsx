"use client";

import { useState } from "react";
import { CustomerBillingView } from "@/features/billing/components/customer-billing-view";
import { cn } from "@/lib/utils";

const SETTINGS_TABS = [
  { id: "business", label: "Business" },
  { id: "agent", label: "Agent" },
  { id: "knowledge", label: "Knowledge" },
  { id: "channels", label: "Channels" },
  { id: "billing", label: "Plan & Billing" },
  { id: "team", label: "Team" },
] as const;

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<(typeof SETTINGS_TABS)[number]["id"]>("business");
  const current = SETTINGS_TABS.find((t) => t.id === activeTab) ?? SETTINGS_TABS[0];

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold tracking-tight text-foreground">Settings</h1>

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
        ) : (
          <p className="text-sm text-muted-foreground">{current.label}</p>
        )}
      </div>
    </div>
  );
}
