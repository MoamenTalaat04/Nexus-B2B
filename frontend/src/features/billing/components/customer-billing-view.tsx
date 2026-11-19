"use client";

import { useEffect, useState, type FormEvent } from "react";
import {
  AlertTriangle,
  Camera,
  Check,
  CreditCard,
  ExternalLink,
  Layers,
  Mail,
  MapPin,
  MessageCircle,
  Plus,
  Send,
  Trash2,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { BorderBeam } from "@/components/ui/border-beam";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  addSandboxPaymentMethod,
  getCustomerBilling,
  removeSandboxPaymentMethod,
  saveBillingAddress,
  selectCustomerPlan,
  type BillingCycle,
  type ChannelBundle,
  type GatewayId,
  type TenantBillingRecord,
} from "@/lib/mock-api";
import { cn } from "@/lib/utils";

type SubscriptionTab = "plan" | "billing" | "invoices";

const CHANNELS: Array<{ id: ChannelBundle; label: string; icon: typeof Layers; multiplier: number }> = [
  { id: "omnichannel", label: "Omnichannel", icon: Layers, multiplier: 1 },
  { id: "whatsapp", label: "WhatsApp", icon: MessageCircle, multiplier: 0.7 },
  { id: "telegram", label: "Telegram", icon: Send, multiplier: 0.55 },
  { id: "instagram", label: "Instagram", icon: Camera, multiplier: 0.65 },
  { id: "email", label: "Email", icon: Mail, multiplier: 0.5 },
];

const PLANS = [
  {
    id: "starter",
    name: "Starter",
    baseMonthlyUsd: 29,
    description: "For automating leads, discovery, and first-touch outreach.",
    quotas: [
      { label: "Messages", value: "3,000" },
      { label: "AI Agents", value: "3" },
      { label: "Team Members", value: "3" },
    ],
    features: [
      "AI-powered prospect discovery",
      "Lead scoring & qualification",
      "Assisted & template outreach",
      "Built-in CRM pipeline",
    ],
    recommended: false,
    custom: false,
  },
  {
    id: "growth",
    name: "Growth",
    baseMonthlyUsd: 99,
    description: "For businesses scaling high-volume B2B pipelines and replies.",
    quotas: [
      { label: "Messages", value: "15,000" },
      { label: "AI Agents", value: "15" },
      { label: "Team Members", value: "10" },
    ],
    features: [
      "Everything in Starter",
      "Autonomous AI Reply Agent",
      "Telegram hot-lead escalation",
      "Cost & conversion analytics",
    ],
    recommended: true,
    custom: false,
  },
  {
    id: "enterprise",
    name: "Enterprise",
    baseMonthlyUsd: 0,
    description: "For established sales orgs with custom volumes & integrations.",
    quotas: [
      { label: "Messages", value: "Unlimited" },
      { label: "AI Agents", value: "Unlimited" },
      { label: "Team Members", value: "Unlimited" },
    ],
    features: [
      "Everything in Growth",
      "Dedicated onboarding & SLA",
      "Custom CRM & webhook sync",
      "Multi-region workspaces",
    ],
    recommended: false,
    custom: true,
  },
] as const;

const SANDBOX_GATEWAYS: Array<{
  id: GatewayId;
  name: string;
  region: string;
  placeholder: string;
  hint: string;
  authUrl: string;
}> = [
  {
    id: "stripe",
    name: "Stripe (Sandbox)",
    region: "International",
    placeholder: "4242 4242 4242 4242",
    hint: "Test Visa card: 4242 •••• •••• 4242 · Exp 12/28 · CVC 424",
    authUrl: "https://dashboard.stripe.com/test/apikeys",
  },
  {
    id: "paypal",
    name: "PayPal (Sandbox)",
    region: "International",
    placeholder: "sb-buyer@personal.example.com",
    hint: "Enter your PayPal Sandbox buyer account email",
    authUrl: "https://developer.paypal.com/dashboard/applications/sandbox",
  },
  {
    id: "paymob",
    name: "Paymob (Egypt Sandbox)",
    region: "Egypt",
    placeholder: "5123 45•• •••• 0008 / 01012345678",
    hint: "Supports Egyptian Meeza, Visa/MC, or Mobile Wallet test numbers",
    authUrl: "https://accept.paymob.com/portal2/en/login",
  },
  {
    id: "fawry",
    name: "Fawry (Egypt Sandbox)",
    region: "Egypt",
    placeholder: "01012345678",
    hint: "Generates a Fawry Pay staging reference number",
    authUrl: "https://developer.fawrystaging.com/",
  },
  {
    id: "instapay",
    name: "InstaPay (Egypt Sandbox)",
    region: "Egypt",
    placeholder: "company@instapay",
    hint: "Instant bank transfer via Egyptian IPA handle",
    authUrl: "https://www.instapay.eg/",
  },
];

export function CustomerBillingView() {
  const [subTab, setSubTab] = useState<SubscriptionTab>("plan");
  const [channel, setChannel] = useState<ChannelBundle>("omnichannel");
  const [cycle, setCycle] = useState<BillingCycle>("monthly");
  const [billing, setBilling] = useState<TenantBillingRecord | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  // Payment Method Sandbox Form
  const [showPaymentForm, setShowPaymentForm] = useState(false);
  const [selectedGateway, setSelectedGateway] = useState<GatewayId>("stripe");
  const [paymentInput, setPaymentInput] = useState("4242 4242 4242 4242");

  // Billing Address Form
  const [showAddressForm, setShowAddressForm] = useState(false);
  const [companyName, setCompanyName] = useState("");
  const [country, setCountry] = useState("Egypt");
  const [city, setCity] = useState("");
  const [street, setStreet] = useState("");
  const [taxId, setTaxId] = useState("");

  useEffect(() => {
    let active = true;
    void getCustomerBilling().then((rec) => {
      if (!active) return;
      setBilling(rec);
      setChannel(rec.channel);
      setCycle(rec.cycle);
      if (rec.billingAddress) {
        setCompanyName(rec.billingAddress.companyName);
        setCountry(rec.billingAddress.country);
        setCity(rec.billingAddress.city);
        setStreet(rec.billingAddress.street);
        setTaxId(rec.billingAddress.taxId ?? "");
      }
    });
    return () => {
      active = false;
    };
  }, []);

  const currentChannel = CHANNELS.find((c) => c.id === channel) ?? CHANNELS[0];

  function computePrice(baseMonthly: number): number {
    if (baseMonthly === 0) return 0;
    const adjusted = Math.round(baseMonthly * currentChannel.multiplier);
    return cycle === "yearly" ? Math.round((adjusted * 10) / 12) : adjusted;
  }

  async function handleSelectPlan(planId: string, planName: string, monthlyPrice: number) {
    const amountUsd = cycle === "yearly" ? monthlyPrice * 12 : monthlyPrice;
    const updated = await selectCustomerPlan({
      planId,
      planName,
      channel,
      cycle,
      amountUsd,
    });
    setBilling(updated);
    setNotice(`Switched to ${planName} (${currentChannel.label}, ${cycle}). Sandbox invoice generated.`);
  }

  async function handleAddPayment(e: FormEvent) {
    e.preventDefault();
    const gw = SANDBOX_GATEWAYS.find((g) => g.id === selectedGateway) ?? SANDBOX_GATEWAYS[0];
    const trimmed = paymentInput.trim() || gw.placeholder;
    const masked =
      selectedGateway === "stripe" || selectedGateway === "paymob"
        ? `•••• ${trimmed.slice(-4)}`
        : trimmed;

    const updated = await addSandboxPaymentMethod({
      gateway: selectedGateway,
      label: gw.name,
      details: masked,
    });
    setBilling(updated);
    setShowPaymentForm(false);
    setNotice(`Authorized ${gw.name} in sandbox mode.`);
  }

  async function handleRemovePayment(id: string) {
    const updated = await removeSandboxPaymentMethod(id);
    setBilling(updated);
  }

  async function handleSaveAddress(e: FormEvent) {
    e.preventDefault();
    const updated = await saveBillingAddress({
      companyName,
      country,
      city,
      street,
      taxId: taxId || undefined,
    });
    setBilling(updated);
    setShowAddressForm(false);
    setNotice("Billing address saved.");
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold tracking-tight text-foreground">Subscriptions</h2>
          <p className="text-xs text-muted-foreground">
            Sandbox billing &amp; channel plans (mock mode — no real charges).
          </p>
        </div>
        {notice && (
          <Badge variant="secondary" className="border border-primary/25 bg-primary-light text-xs text-emerald-dark dark:bg-surface-secondary dark:text-lime-300">
            {notice}
          </Badge>
        )}
      </div>

      {/* 3 Sub-Tabs: Plan, Billing, Invoices */}
      <div className="flex gap-6 border-b border-border">
        {(
          [
            { id: "plan", label: "Plan" },
            { id: "billing", label: "Billing" },
            { id: "invoices", label: "Invoices" },
          ] as const
        ).map((tab) => (
          <button
            key={tab.id}
            type="button"
            onClick={() => setSubTab(tab.id)}
            className={cn(
              "border-b-2 pb-2.5 text-sm font-semibold transition-colors",
              subTab === tab.id
                ? "border-primary text-primary dark:text-lime-300"
                : "border-transparent text-muted-foreground hover:text-foreground",
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* TAB 1: PLAN */}
      {subTab === "plan" && (
        <div className="space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-4">
            {/* Channel Selector Pills */}
            <div className="flex flex-wrap items-center gap-2">
              {CHANNELS.map((c) => {
                const Icon = c.icon;
                const active = channel === c.id;
                return (
                  <button
                    key={c.id}
                    type="button"
                    onClick={() => setChannel(c.id)}
                    className={cn(
                      "inline-flex items-center gap-2 rounded-xl border px-3.5 py-2 text-xs font-semibold transition-colors sm:text-sm",
                      active
                        ? "border-primary/40 bg-primary/12 text-primary dark:bg-lime-500/15 dark:text-lime-300"
                        : "border-border bg-surface text-muted-foreground hover:bg-surface-secondary hover:text-foreground",
                    )}
                  >
                    <Icon className="size-4" />
                    {c.label}
                  </button>
                );
              })}
            </div>

            {/* Monthly / Yearly Toggle */}
            <div className="flex items-center gap-2.5">
              <button
                type="button"
                onClick={() => setCycle("monthly")}
                className={cn(
                  "text-xs font-semibold",
                  cycle === "monthly" ? "text-foreground" : "text-muted-foreground",
                )}
              >
                Monthly
              </button>
              <button
                type="button"
                aria-label="Toggle yearly billing"
                onClick={() => setCycle((prev) => (prev === "monthly" ? "yearly" : "monthly"))}
                className={cn(
                  "relative h-6 w-11 rounded-full transition-colors",
                  cycle === "yearly" ? "bg-primary" : "bg-border",
                )}
              >
                <span
                  className={cn(
                    "absolute top-0.5 left-0.5 size-5 rounded-full bg-white shadow-xs transition-transform",
                    cycle === "yearly" && "translate-x-5",
                  )}
                />
              </button>
              <button
                type="button"
                onClick={() => setCycle("yearly")}
                className={cn(
                  "text-xs font-semibold",
                  cycle === "yearly" ? "text-foreground" : "text-muted-foreground",
                )}
              >
                Yearly
              </button>
              <Badge className="bg-primary/15 text-[11px] font-bold text-primary dark:text-lime-300">
                2 Months FREE
              </Badge>
            </div>
          </div>

          {/* 3 Pricing Cards */}
          <div className="grid gap-6 lg:grid-cols-3">
            {PLANS.map((plan) => {
              const price = computePrice(plan.baseMonthlyUsd);
              const isCurrent = billing?.activePlanId === plan.id && billing?.channel === channel;

              return (
                <Card
                  key={plan.id}
                  className={cn(
                    "relative flex h-full flex-col justify-between overflow-hidden rounded-2xl bg-card",
                    plan.recommended ? "border-transparent shadow-lg shadow-lime-950/10" : "border-border shadow-xs",
                  )}
                >
                  {plan.recommended && (
                    <BorderBeam
                      duration={6}
                      size={360}
                      reverse
                      borderWidth={2}
                      colorFrom="#10B981"
                      colorTo="#84CC16"
                    />
                  )}
                  <CardHeader>
                    <div className="flex items-center justify-between">
                      <CardTitle className="text-lg font-bold text-foreground">{plan.name}</CardTitle>
                      {plan.recommended && (
                        <Badge className="border-0 bg-gradient-to-r from-[#10B981] to-[#84CC16] font-bold text-[#0A140C]">
                          Recommended
                        </Badge>
                      )}
                    </div>
                    <div className="mt-2">
                      {plan.custom ? (
                        <p className="text-2xl font-extrabold text-foreground">Custom Pricing</p>
                      ) : (
                        <p className="text-3xl font-extrabold text-foreground">
                          ${price}
                          <span className="text-sm font-medium text-muted-foreground"> / Month</span>
                        </p>
                      )}
                    </div>
                    <p className="mt-1 text-xs text-muted-foreground">{plan.description}</p>
                  </CardHeader>

                  <CardContent className="space-y-4">
                    <div className="space-y-1.5 rounded-xl border border-border/70 bg-surface/60 p-3 text-xs">
                      {plan.quotas.map((q) => (
                        <div key={q.label} className="flex items-center justify-between">
                          <span className="text-muted-foreground">{q.label}</span>
                          <span className="font-bold text-foreground">{q.value}</span>
                        </div>
                      ))}
                    </div>

                    <div className="space-y-2">
                      {plan.features.map((feat) => (
                        <div key={feat} className="flex items-start gap-2 text-xs text-foreground">
                          <Check className="mt-0.5 size-3.5 shrink-0 text-primary" />
                          <span>{feat}</span>
                        </div>
                      ))}
                    </div>
                  </CardContent>

                  <CardFooter>
                    {plan.custom ? (
                      <Button variant="outline" className="w-full rounded-xl font-semibold">
                        Contact Us
                      </Button>
                    ) : (
                      <Button
                        disabled={isCurrent}
                        onClick={() => handleSelectPlan(plan.id, plan.name, price)}
                        className={cn(
                          "w-full rounded-xl font-bold",
                          plan.recommended
                            ? "bg-gradient-to-r from-[#10B981] to-[#84CC16] text-[#0A140C] hover:opacity-90"
                            : "bg-surface text-foreground hover:bg-surface-secondary",
                        )}
                      >
                        {isCurrent ? "Current Plan" : "Change Plan"}
                      </Button>
                    )}
                  </CardFooter>
                </Card>
              );
            })}
          </div>
        </div>
      )}

      {/* TAB 2: BILLING (Sandbox Payment Methods & Billing Address) */}
      {subTab === "billing" && (
        <div className="grid gap-6 lg:grid-cols-2">
          {/* Payment Method */}
          <Card className="rounded-2xl border-border bg-card">
            <CardHeader>
              <CardTitle className="text-base font-bold">Payment Method</CardTitle>
              <p className="text-xs text-muted-foreground">
                Connect a sandbox payment method (Stripe, PayPal, Paymob, Fawry, InstaPay).
              </p>
            </CardHeader>
            <CardContent className="space-y-4">
              {billing && billing.paymentMethods.length > 0 && (
                <div className="space-y-2.5">
                  {billing.paymentMethods.map((pm) => (
                    <div
                      key={pm.id}
                      className="flex items-center justify-between rounded-xl border border-border bg-surface/60 px-4 py-3"
                    >
                      <div className="flex items-center gap-3">
                        <CreditCard className="size-4 text-primary" />
                        <div>
                          <p className="text-sm font-semibold text-foreground">{pm.label}</p>
                          <p className="text-xs text-muted-foreground">{pm.details}</p>
                        </div>
                      </div>
                      <Button
                        variant="ghost"
                        size="icon"
                        aria-label="Remove payment method"
                        onClick={() => handleRemovePayment(pm.id)}
                        className="text-muted-foreground hover:text-destructive"
                      >
                        <Trash2 className="size-4" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}

              {!showPaymentForm && (!billing || billing.paymentMethods.length === 0) && (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-8 text-center">
                  <div className="mb-3 flex size-11 items-center justify-center rounded-xl bg-primary/12 text-primary">
                    <CreditCard className="size-5" />
                  </div>
                  <p className="text-sm font-bold text-foreground">No payment method added</p>
                  <p className="mt-1 max-w-xs text-xs text-muted-foreground">
                    Add a sandbox card, PayPal, or Egyptian payment method to test checkout.
                  </p>
                  <Button
                    onClick={() => setShowPaymentForm(true)}
                    className="mt-4 rounded-xl bg-gradient-to-r from-[#10B981] to-[#84CC16] font-bold text-[#0A140C]"
                  >
                    <Plus className="mr-1.5 size-4" />
                    Add Payment Method
                  </Button>
                </div>
              )}

              {!showPaymentForm && billing && billing.paymentMethods.length > 0 && (
                <Button variant="outline" onClick={() => setShowPaymentForm(true)} className="w-full rounded-xl">
                  <Plus className="mr-1.5 size-4" />
                  Add Another Sandbox Method
                </Button>
              )}

              {showPaymentForm && (
                <form onSubmit={handleAddPayment} className="space-y-4 rounded-xl border border-border bg-surface/50 p-4">
                  <div className="space-y-2">
                    <Label className="text-xs font-semibold">Select Sandbox Gateway</Label>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                      {SANDBOX_GATEWAYS.map((gw) => (
                        <button
                          key={gw.id}
                          type="button"
                          onClick={() => {
                            setSelectedGateway(gw.id);
                            setPaymentInput(gw.placeholder);
                          }}
                          className={cn(
                            "rounded-lg border px-3 py-2 text-left text-xs transition-colors",
                            selectedGateway === gw.id
                              ? "border-primary bg-primary/10 font-semibold text-primary"
                              : "border-border bg-card text-foreground hover:bg-surface-secondary",
                          )}
                        >
                          <span className="block">{gw.name}</span>
                          <span className="text-[10px] text-muted-foreground">{gw.region}</span>
                        </button>
                      ))}
                    </div>
                  </div>

                  {(() => {
                    const activeGw = SANDBOX_GATEWAYS.find((g) => g.id === selectedGateway) ?? SANDBOX_GATEWAYS[0];
                    return (
                      <div className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor="sandbox-payment-input" className="text-xs font-semibold">
                            Sandbox Credentials / Account
                          </Label>
                          <a
                            href={activeGw.authUrl}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center gap-1 text-[11px] font-semibold text-primary hover:underline"
                          >
                            Authorize in Sandbox
                            <ExternalLink className="size-3" />
                          </a>
                        </div>
                        <Input
                          id="sandbox-payment-input"
                          value={paymentInput}
                          onChange={(e) => setPaymentInput(e.target.value)}
                          placeholder={activeGw.placeholder}
                          required
                        />
                        <p className="text-[11px] text-muted-foreground">{activeGw.hint}</p>
                      </div>
                    );
                  })()}

                  <div className="flex gap-2">
                    <Button
                      type="submit"
                      className="flex-1 rounded-xl bg-gradient-to-r from-[#10B981] to-[#84CC16] font-bold text-[#0A140C]"
                    >
                      Save Sandbox Method
                    </Button>
                    <Button type="button" variant="ghost" onClick={() => setShowPaymentForm(false)}>
                      Cancel
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>

          {/* Billing Address */}
          <Card className="rounded-2xl border-border bg-card">
            <CardHeader>
              <CardTitle className="text-base font-bold">Billing Address</CardTitle>
              <p className="text-xs text-muted-foreground">
                Company billing details printed on sandbox invoices.
              </p>
            </CardHeader>
            <CardContent>
              {!showAddressForm && !billing?.billingAddress && (
                <div className="flex flex-col items-center justify-center rounded-xl border border-dashed border-border py-10 text-center">
                  <div className="mb-3 flex size-11 items-center justify-center rounded-xl bg-primary/12 text-primary">
                    <MapPin className="size-5" />
                  </div>
                  <p className="max-w-xs text-xs text-muted-foreground">
                    Please add your billing address to complete your purchase and keep invoices accurate.
                  </p>
                  <Button
                    onClick={() => setShowAddressForm(true)}
                    className="mt-4 rounded-xl bg-gradient-to-r from-[#10B981] to-[#84CC16] font-bold text-[#0A140C]"
                  >
                    Add Your Billing Address
                  </Button>
                </div>
              )}

              {!showAddressForm && billing?.billingAddress && (
                <div className="space-y-3 rounded-xl border border-border bg-surface/60 p-4 text-sm">
                  <p className="font-bold text-foreground">{billing.billingAddress.companyName}</p>
                  <p className="text-xs text-muted-foreground">
                    {billing.billingAddress.street}, {billing.billingAddress.city}, {billing.billingAddress.country}
                  </p>
                  {billing.billingAddress.taxId && (
                    <p className="text-xs text-muted-foreground">Tax ID: {billing.billingAddress.taxId}</p>
                  )}
                  <Button variant="outline" size="sm" onClick={() => setShowAddressForm(true)}>
                    Edit Address
                  </Button>
                </div>
              )}

              {showAddressForm && (
                <form onSubmit={handleSaveAddress} className="space-y-3">
                  <div className="grid gap-1.5">
                    <Label htmlFor="bill-company" className="text-xs">Company Name</Label>
                    <Input id="bill-company" required value={companyName} onChange={(e) => setCompanyName(e.target.value)} />
                  </div>
                  <div className="grid grid-cols-2 gap-3">
                    <div className="grid gap-1.5">
                      <Label htmlFor="bill-country" className="text-xs">Country</Label>
                      <Input id="bill-country" required value={country} onChange={(e) => setCountry(e.target.value)} />
                    </div>
                    <div className="grid gap-1.5">
                      <Label htmlFor="bill-city" className="text-xs">City</Label>
                      <Input id="bill-city" required value={city} onChange={(e) => setCity(e.target.value)} />
                    </div>
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="bill-street" className="text-xs">Street Address</Label>
                    <Input id="bill-street" required value={street} onChange={(e) => setStreet(e.target.value)} />
                  </div>
                  <div className="grid gap-1.5">
                    <Label htmlFor="bill-tax" className="text-xs">Tax ID (Optional)</Label>
                    <Input id="bill-tax" value={taxId} onChange={(e) => setTaxId(e.target.value)} />
                  </div>
                  <div className="flex gap-2 pt-2">
                    <Button type="submit" className="rounded-xl bg-gradient-to-r from-[#10B981] to-[#84CC16] font-bold text-[#0A140C]">
                      Save Address
                    </Button>
                    <Button type="button" variant="ghost" onClick={() => setShowAddressForm(false)}>
                      Cancel
                    </Button>
                  </div>
                </form>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {/* TAB 3: INVOICES */}
      {subTab === "invoices" && (
        <Card className="rounded-2xl border-border bg-card">
          <CardHeader>
            <CardTitle className="text-base font-bold">Invoices</CardTitle>
          </CardHeader>
          <CardContent>
            {!billing || billing.invoices.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <div className="mb-3 flex size-12 items-center justify-center rounded-xl bg-amber-500/15 text-amber-600 dark:text-amber-400">
                  <AlertTriangle className="size-6" />
                </div>
                <p className="text-sm font-bold text-foreground">No Invoices Found!</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  Your invoice will appear here after you make any purchase.
                </p>
              </div>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs sm:text-sm">
                  <thead className="border-b border-border text-muted-foreground">
                    <tr>
                      <th className="py-2.5 pr-4 font-semibold">Invoice</th>
                      <th className="py-2.5 pr-4 font-semibold">Plan</th>
                      <th className="py-2.5 pr-4 font-semibold">Channel</th>
                      <th className="py-2.5 pr-4 font-semibold">Gateway</th>
                      <th className="py-2.5 pr-4 font-semibold">Amount</th>
                      <th className="py-2.5 font-semibold">Status</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {billing.invoices.map((inv) => (
                      <tr key={inv.id}>
                        <td className="py-3 pr-4 font-semibold text-foreground">{inv.id}</td>
                        <td className="py-3 pr-4 text-foreground">{inv.planName} ({inv.cycle})</td>
                        <td className="py-3 pr-4 capitalize text-muted-foreground">{inv.channel}</td>
                        <td className="py-3 pr-4 capitalize text-muted-foreground">{inv.gateway}</td>
                        <td className="py-3 pr-4 font-bold text-foreground">${inv.amountUsd}</td>
                        <td className="py-3">
                          <Badge className="bg-primary/15 text-[11px] text-primary capitalize dark:text-lime-300">
                            {inv.status}
                          </Badge>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}
