import type { ProductIn, RegionIn } from "@/lib/settings-types";

export interface FAQItem {
  q: string;
  a: string;
}

export interface CompanyProfileData {
  company_name: string;
  one_liner: string;
  products: ProductIn[];
  differentiators: string[];
  target_customer_summary: string;
  allowed_offers: string;
  max_discount_percent: number;
  faqs: FAQItem[];
  tone: string;
  language: string;
}

export type BusinessSize = "micro" | "small" | "medium" | "large" | "any";

export interface ICPData {
  summary: string;
  target_business_types: string[];
  include_keywords: string[];
  exclude_keywords: string[];
  google_place_types: string[];
  regions: RegionIn[];
  business_size: BusinessSize;
  must_have: string[];
  nice_to_have: string[];
  disqualifiers: string[];
  value_proposition: string;
  pain_points: string[];
  outreach_angle: string;
  language: string;
}

export interface IcpVersionSummary {
  id: string;
  version: number;
  source: string;
  is_active: boolean;
  notes: string | null;
  created_at: string;
}

export interface IcpVersionOut extends IcpVersionSummary {
  company_profile: CompanyProfileData;
  icp: ICPData;
}

export interface IcpVersionList {
  items: IcpVersionSummary[];
  total: number;
}

export interface AgentRunStatusOut {
  id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  error: string | null;
}
