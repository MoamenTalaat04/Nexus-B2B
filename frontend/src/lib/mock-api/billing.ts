import { requireAuthenticatedUser } from "@/lib/mock-api/auth";
import { MockApiError } from "@/lib/mock-api/types";

export type ChannelBundle = "omnichannel" | "whatsapp" | "telegram" | "instagram" | "email";
export type BillingCycle = "monthly" | "yearly";
export type GatewayId = "stripe" | "paypal" | "paymob" | "fawry" | "instapay" | "paddle";

export interface SandboxPaymentMethod {
  id: string;
  gateway: GatewayId;
  label: string;
  details: string;
  isDefault: boolean;
  addedAt: string;
}

export interface BillingAddress {
  companyName: string;
  country: string;
  city: string;
  street: string;
  taxId?: string;
}

export interface SandboxInvoice {
  id: string;
  tenantId: string;
  planName: string;
  channel: ChannelBundle;
  cycle: BillingCycle;
  amountUsd: number;
  gateway: GatewayId | "sandbox_trial";
  status: "paid" | "pending";
  createdAt: string;
}

export interface TenantBillingRecord {
  tenantId: string;
  activePlanId: string;
  channel: ChannelBundle;
  cycle: BillingCycle;
  paymentMethods: SandboxPaymentMethod[];
  billingAddress: BillingAddress | null;
  invoices: SandboxInvoice[];
}

export interface PlatformGatewayConfig {
  id: GatewayId;
  name: string;
  region: "International" | "Egypt";
  description: string;
  authUrl: string;
  mode: "sandbox" | "live";
  connected: boolean;
  sandboxAccountLabel: string;
  lastAuthorizedAt: string | null;
}

interface MockBillingDatabase {
  version: 1;
  tenantBilling: Record<string, TenantBillingRecord>;
  gateways: PlatformGatewayConfig[];
}

export const MOCK_BILLING_STORAGE_KEY = "nexus_mock_billing_v1";

const DEFAULT_GATEWAYS: PlatformGatewayConfig[] = [
  {
    id: "stripe",
    name: "Stripe",
    region: "International",
    description: "Credit & debit cards, Apple Pay, and automated recurring subscriptions.",
    authUrl: "https://dashboard.stripe.com/test/apikeys",
    mode: "sandbox",
    connected: true,
    sandboxAccountLabel: "acct_sandbox_nexus_stripe",
    lastAuthorizedAt: "2026-11-19T10:00:00.000Z",
  },
  {
    id: "paypal",
    name: "PayPal",
    region: "International",
    description: "PayPal Checkout & Vaulted Billing Agreements (Sandbox REST API).",
    authUrl: "https://developer.paypal.com/dashboard/applications/sandbox",
    mode: "sandbox",
    connected: true,
    sandboxAccountLabel: "sb-nexus-merchant@business.example.com",
    lastAuthorizedAt: "2026-11-19T10:00:00.000Z",
  },
  {
    id: "paddle",
    name: "Paddle",
    region: "International",
    description: "Merchant-of-record SaaS billing, global VAT & tax compliance.",
    authUrl: "https://sandbox-vendors.paddle.com/",
    mode: "sandbox",
    connected: false,
    sandboxAccountLabel: "",
    lastAuthorizedAt: null,
  },
  {
    id: "paymob",
    name: "Paymob",
    region: "Egypt",
    description: "Egyptian cards, Meeza, and mobile wallets (Vodafone / Orange / Etisalat Cash).",
    authUrl: "https://accept.paymob.com/portal2/en/login",
    mode: "sandbox",
    connected: true,
    sandboxAccountLabel: "paymob_sandbox_eg_01",
    lastAuthorizedAt: "2026-11-19T10:00:00.000Z",
  },
  {
    id: "fawry",
    name: "Fawry",
    region: "Egypt",
    description: "Fawry Pay reference-code cash & kiosk payments across Egypt.",
    authUrl: "https://developer.fawrystaging.com/",
    mode: "sandbox",
    connected: false,
    sandboxAccountLabel: "",
    lastAuthorizedAt: null,
  },
  {
    id: "instapay",
    name: "InstaPay",
    region: "Egypt",
    description: "Instant Egyptian bank transfers via IPA handle verification.",
    authUrl: "https://www.instapay.eg/",
    mode: "sandbox",
    connected: false,
    sandboxAccountLabel: "",
    lastAuthorizedAt: null,
  },
];

let memoryBillingDb: MockBillingDatabase | null = null;

function createInitialBillingDb(): MockBillingDatabase {
  return {
    version: 1,
    tenantBilling: {
      tenant_001: {
        tenantId: "tenant_001",
        activePlanId: "growth",
        channel: "omnichannel",
        cycle: "monthly",
        paymentMethods: [],
        billingAddress: null,
        invoices: [],
      },
      tenant_002: {
        tenantId: "tenant_002",
        activePlanId: "starter",
        channel: "whatsapp",
        cycle: "monthly",
        paymentMethods: [],
        billingAddress: null,
        invoices: [],
      },
    },
    gateways: DEFAULT_GATEWAYS,
  };
}

function readBillingDb(): MockBillingDatabase {
  if (typeof window !== "undefined" && typeof window.localStorage !== "undefined") {
    const raw = window.localStorage.getItem(MOCK_BILLING_STORAGE_KEY);
    if (raw) {
      try {
        const parsed = JSON.parse(raw) as MockBillingDatabase;
        if (parsed && parsed.version === 1 && parsed.tenantBilling && Array.isArray(parsed.gateways)) {
          return parsed;
        }
      } catch {
        // Fallback to seed if corrupted.
      }
    }
    const initial = createInitialBillingDb();
    window.localStorage.setItem(MOCK_BILLING_STORAGE_KEY, JSON.stringify(initial));
    return initial;
  }
  if (!memoryBillingDb) {
    memoryBillingDb = createInitialBillingDb();
  }
  return memoryBillingDb;
}

function writeBillingDb(db: MockBillingDatabase): void {
  if (typeof window !== "undefined" && typeof window.localStorage !== "undefined") {
    window.localStorage.setItem(MOCK_BILLING_STORAGE_KEY, JSON.stringify(db));
  } else {
    memoryBillingDb = db;
  }
}

function ensureTenantRecord(db: MockBillingDatabase, tenantId: string): TenantBillingRecord {
  if (!db.tenantBilling[tenantId]) {
    db.tenantBilling[tenantId] = {
      tenantId,
      activePlanId: "starter",
      channel: "whatsapp",
      cycle: "monthly",
      paymentMethods: [],
      billingAddress: null,
      invoices: [],
    };
  }
  return db.tenantBilling[tenantId];
}

export async function getCustomerBilling(): Promise<TenantBillingRecord> {
  const user = await requireAuthenticatedUser();
  if (!user.tenantId) {
    throw new MockApiError("forbidden", "Customer workspace required.", 403);
  }
  const db = readBillingDb();
  const record = ensureTenantRecord(db, user.tenantId);
  writeBillingDb(db);
  return record;
}

export async function selectCustomerPlan(input: {
  planId: string;
  planName: string;
  channel: ChannelBundle;
  cycle: BillingCycle;
  amountUsd: number;
}): Promise<TenantBillingRecord> {
  const user = await requireAuthenticatedUser();
  if (!user.tenantId) {
    throw new MockApiError("forbidden", "Customer workspace required.", 403);
  }
  const db = readBillingDb();
  const record = ensureTenantRecord(db, user.tenantId);
  const defaultMethod = record.paymentMethods.find((m) => m.isDefault) ?? record.paymentMethods[0];

  const invoice: SandboxInvoice = {
    id: `INV-${Date.now().toString().slice(-6)}`,
    tenantId: user.tenantId,
    planName: input.planName,
    channel: input.channel,
    cycle: input.cycle,
    amountUsd: input.amountUsd,
    gateway: defaultMethod ? defaultMethod.gateway : "sandbox_trial",
    status: "paid",
    createdAt: new Date().toISOString(),
  };

  record.activePlanId = input.planId;
  record.channel = input.channel;
  record.cycle = input.cycle;
  record.invoices = [invoice, ...record.invoices];

  writeBillingDb(db);
  return { ...record };
}

export async function addSandboxPaymentMethod(input: {
  gateway: GatewayId;
  label: string;
  details: string;
}): Promise<TenantBillingRecord> {
  const user = await requireAuthenticatedUser();
  if (!user.tenantId) {
    throw new MockApiError("forbidden", "Customer workspace required.", 403);
  }
  const db = readBillingDb();
  const record = ensureTenantRecord(db, user.tenantId);

  const method: SandboxPaymentMethod = {
    id: `pm_sb_${Date.now().toString(36)}`,
    gateway: input.gateway,
    label: input.label,
    details: input.details,
    isDefault: record.paymentMethods.length === 0,
    addedAt: new Date().toISOString(),
  };

  record.paymentMethods = [...record.paymentMethods, method];
  writeBillingDb(db);
  return { ...record };
}

export async function removeSandboxPaymentMethod(methodId: string): Promise<TenantBillingRecord> {
  const user = await requireAuthenticatedUser();
  if (!user.tenantId) {
    throw new MockApiError("forbidden", "Customer workspace required.", 403);
  }
  const db = readBillingDb();
  const record = ensureTenantRecord(db, user.tenantId);
  record.paymentMethods = record.paymentMethods.filter((m) => m.id !== methodId);
  writeBillingDb(db);
  return { ...record };
}

export async function saveBillingAddress(address: BillingAddress): Promise<TenantBillingRecord> {
  const user = await requireAuthenticatedUser();
  if (!user.tenantId) {
    throw new MockApiError("forbidden", "Customer workspace required.", 403);
  }
  const db = readBillingDb();
  const record = ensureTenantRecord(db, user.tenantId);
  record.billingAddress = address;
  writeBillingDb(db);
  return { ...record };
}

export async function getPlatformBillingOverview(): Promise<{
  mrrUsd: number;
  totalRevenueUsd: number;
  gatewayFeesUsd: number;
  netProfitUsd: number;
  activePaidWorkspaces: number;
  gateways: PlatformGatewayConfig[];
  recentInvoices: SandboxInvoice[];
}> {
  const user = await requireAuthenticatedUser();
  if (user.role !== "super_admin") {
    throw new MockApiError("forbidden", "Super Admin privileges required for platform billing.", 403);
  }

  const db = readBillingDb();
  const allInvoices = Object.values(db.tenantBilling).flatMap((t) => t.invoices);
  const sandboxSum = allInvoices.reduce((acc, inv) => acc + inv.amountUsd, 0);

  // Baseline demo revenue + any new sandbox customer invoices
  const mrrUsd = 4820 + sandboxSum;
  const totalRevenueUsd = 28920 + sandboxSum;
  const gatewayFeesUsd = Math.round(totalRevenueUsd * 0.029);
  const netProfitUsd = totalRevenueUsd - gatewayFeesUsd;

  return {
    mrrUsd,
    totalRevenueUsd,
    gatewayFeesUsd,
    netProfitUsd,
    activePaidWorkspaces: Object.keys(db.tenantBilling).length + 46,
    gateways: db.gateways,
    recentInvoices: allInvoices.slice(0, 10),
  };
}

export async function authorizePlatformGateway(input: {
  gatewayId: GatewayId;
  sandboxAccountLabel: string;
  connect: boolean;
}): Promise<PlatformGatewayConfig[]> {
  const user = await requireAuthenticatedUser();
  if (user.role !== "super_admin") {
    throw new MockApiError("forbidden", "Super Admin privileges required to authorize gateways.", 403);
  }

  const db = readBillingDb();
  db.gateways = db.gateways.map((gw) =>
    gw.id === input.gatewayId
      ? {
          ...gw,
          connected: input.connect,
          sandboxAccountLabel: input.connect ? input.sandboxAccountLabel.trim() || `${gw.id}_sandbox_connected` : "",
          lastAuthorizedAt: input.connect ? new Date().toISOString() : null,
        }
      : gw,
  );
  writeBillingDb(db);
  return db.gateways;
}

