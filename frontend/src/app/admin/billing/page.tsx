"use client";

import { useEffect, useState } from "react";
import {
  CheckCircle2,
  CreditCard,
  DollarSign,
  ExternalLink,
  Globe,
  ShieldCheck,
  TrendingUp,
} from "lucide-react";
import { RouteGuard } from "@/components/auth/route-guard";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import {
  authorizePlatformGateway,
  getPlatformBillingOverview,
  type GatewayId,
  type PlatformGatewayConfig,
  type SandboxInvoice,
} from "@/lib/mock-api";
import { cn } from "@/lib/utils";

function SuperAdminBillingContent() {
  const [overview, setOverview] = useState<{
    mrrUsd: number;
    totalRevenueUsd: number;
    gatewayFeesUsd: number;
    netProfitUsd: number;
    activePaidWorkspaces: number;
    gateways: PlatformGatewayConfig[];
    recentInvoices: SandboxInvoice[];
  } | null>(null);
  const [draftLabels, setDraftLabels] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    void getPlatformBillingOverview().then((data) => {
      if (!active) return;
      setOverview(data);
      const labels: Record<string, string> = {};
      for (const gw of data.gateways) {
        labels[gw.id] = gw.sandboxAccountLabel;
      }
      setDraftLabels(labels);
    });
    return () => {
      active = false;
    };
  }, []);

  async function handleToggleAuthorize(gw: PlatformGatewayConfig) {
    const nextConnect = !gw.connected;
    const updatedGateways = await authorizePlatformGateway({
      gatewayId: gw.id as GatewayId,
      sandboxAccountLabel: draftLabels[gw.id] ?? "",
      connect: nextConnect,
    });
    setOverview((prev) => (prev ? { ...prev, gateways: updatedGateways } : prev));
    setNotice(
      nextConnect
        ? `${gw.name} authorized and connected in Sandbox mode.`
        : `${gw.name} disconnected.`,
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-bold tracking-tight text-foreground">Billing &amp; Revenue</h1>
            <Badge className="bg-primary/15 text-[11px] font-bold text-primary dark:text-lime-300">
              Super Admin Only
            </Badge>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">
            Platform revenue overview and sandbox payment gateway authorizations (International &amp; Egypt).
          </p>
        </div>

        {notice && (
          <Badge variant="secondary" className="border border-primary/25 bg-primary-light text-xs text-emerald-dark dark:bg-surface-secondary dark:text-lime-300">
            {notice}
          </Badge>
        )}
      </div>

      {/* Revenue & Profit Metrics */}
      {overview && (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Card className="rounded-2xl border-border bg-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Monthly Recurring (MRR)</span>
                <DollarSign className="size-4 text-primary" />
              </div>
              <p className="mt-2 text-2xl font-extrabold text-foreground">
                ${overview.mrrUsd.toLocaleString()}
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-border bg-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Gross Revenue (YTD)</span>
                <TrendingUp className="size-4 text-primary" />
              </div>
              <p className="mt-2 text-2xl font-extrabold text-foreground">
                ${overview.totalRevenueUsd.toLocaleString()}
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-border bg-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Net Profit (After Fees)</span>
                <ShieldCheck className="size-4 text-primary" />
              </div>
              <p className="mt-2 text-2xl font-extrabold text-primary">
                ${overview.netProfitUsd.toLocaleString()}
              </p>
              <p className="mt-0.5 text-[11px] text-muted-foreground">
                Est. gateway fees: ${overview.gatewayFeesUsd.toLocaleString()}
              </p>
            </CardContent>
          </Card>

          <Card className="rounded-2xl border-border bg-card">
            <CardContent className="p-5">
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>Paid Workspaces</span>
                <CreditCard className="size-4 text-primary" />
              </div>
              <p className="mt-2 text-2xl font-extrabold text-foreground">
                {overview.activePaidWorkspaces}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Payment Gateways Authorization */}
      <div className="space-y-4">
        <div>
          <h2 className="text-base font-bold text-foreground">Payment Gateways &amp; Authorization</h2>
          <p className="text-xs text-muted-foreground">
            Authorize sandbox merchant accounts directly from the Admin Portal or open the provider dashboard.
          </p>
        </div>

        <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
          {overview?.gateways.map((gw) => (
            <Card key={gw.id} className="flex flex-col justify-between rounded-2xl border-border bg-card">
              <CardHeader className="pb-3">
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Globe className="size-4 text-primary" />
                    <CardTitle className="text-base font-bold">{gw.name}</CardTitle>
                  </div>
                  <Badge
                    className={cn(
                      "text-[10px] font-bold",
                      gw.connected
                        ? "bg-primary/15 text-primary dark:text-lime-300"
                        : "bg-surface-secondary text-muted-foreground",
                    )}
                  >
                    {gw.connected ? "Connected · Sandbox" : "Not Connected"}
                  </Badge>
                </div>
                <p className="text-[11px] font-semibold text-muted-foreground">{gw.region}</p>
                <p className="mt-1 text-xs text-muted-foreground">{gw.description}</p>
              </CardHeader>

              <CardContent className="space-y-3 pt-0">
                <Input
                  value={draftLabels[gw.id] ?? ""}
                  onChange={(e) => setDraftLabels((prev) => ({ ...prev, [gw.id]: e.target.value }))}
                  placeholder={`Sandbox merchant / account ID for ${gw.name}`}
                  className="h-9 text-xs"
                />

                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    onClick={() => handleToggleAuthorize(gw)}
                    variant={gw.connected ? "outline" : "default"}
                    className={cn(
                      "flex-1 rounded-xl text-xs font-bold",
                      !gw.connected &&
                        "bg-gradient-to-r from-[#10B981] to-[#84CC16] text-[#0A140C] hover:opacity-90",
                    )}
                  >
                    {gw.connected ? (
                      <>
                        <CheckCircle2 className="mr-1.5 size-3.5 text-primary" />
                        Disconnect
                      </>
                    ) : (
                      "Authorize in Portal"
                    )}
                  </Button>

                  <Button
                    size="sm"
                    variant="ghost"
                    className="rounded-xl text-xs"
                    render={
                      <a href={gw.authUrl} target="_blank" rel="noreferrer">
                        Portal
                        <ExternalLink className="ml-1 size-3" />
                      </a>
                    }
                  />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      {/* Recent Sandbox Transactions */}
      <Card className="rounded-2xl border-border bg-card">
        <CardHeader>
          <CardTitle className="text-base font-bold">Recent Sandbox Customer Transactions</CardTitle>
        </CardHeader>
        <CardContent>
          {!overview || overview.recentInvoices.length === 0 ? (
            <p className="text-xs text-muted-foreground">
              No sandbox customer purchases recorded yet. Switch a plan in a customer workspace to test live aggregation.
            </p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs sm:text-sm">
                <thead className="border-b border-border text-muted-foreground">
                  <tr>
                    <th className="py-2 pr-4 font-semibold">Invoice</th>
                    <th className="py-2 pr-4 font-semibold">Tenant</th>
                    <th className="py-2 pr-4 font-semibold">Plan</th>
                    <th className="py-2 pr-4 font-semibold">Gateway</th>
                    <th className="py-2 font-semibold">Amount</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {overview.recentInvoices.map((inv) => (
                    <tr key={inv.id}>
                      <td className="py-2.5 pr-4 font-semibold">{inv.id}</td>
                      <td className="py-2.5 pr-4 text-muted-foreground">{inv.tenantId}</td>
                      <td className="py-2.5 pr-4">{inv.planName} ({inv.channel})</td>
                      <td className="py-2.5 pr-4 capitalize text-muted-foreground">{inv.gateway}</td>
                      <td className="py-2.5 font-bold text-primary">${inv.amountUsd}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdminBillingPage() {
  return (
    <RouteGuard allowedRoles={["super_admin"]}>
      <SuperAdminBillingContent />
    </RouteGuard>
  );
}
