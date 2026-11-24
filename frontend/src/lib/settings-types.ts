import type { AutonomyMode, FirstTouchMode, OutreachPurpose } from "@/lib/types";

export interface ProductIn {
  kind?: "product" | "service";
  name: string;
  description: string;
  price_range?: string | null;
  min_order?: string | null;
}

export interface RegionIn {
  country?: string;
  governorate: string;
  cities: string[];
  lat?: number | null;
  lng?: number | null;
  radius_km?: number | null;
}

export interface SequenceStepIn {
  day_offset: number;
  purpose: OutreachPurpose;
  template: string;
}

export interface SettingsOut {
  company_name: string;
  website: string | null;
  description: string;
  ideal_customer_text: string;
  products: ProductIn[];
  target_regions: RegionIn[];
  language: string;
  tone: "friendly" | "formal";
  allowed_offers: string;
  max_discount_percent: number;
  autonomy_mode: AutonomyMode;
  first_touch_mode: FirstTouchMode;
  agent_enabled: boolean;
  daily_new_leads_target: number;
  daily_send_cap: number;
  quiet_hours_start: string;
  quiet_hours_end: string;
  working_days: number[];
  score_threshold: number;
  sequence_steps: SequenceStepIn[];
  demo_mode: boolean;
  demo_whitelist: string[];
  onboarding_completed: boolean;
  telegram_connected: boolean;
  warnings: string[];
}

export type SettingsUpdate = Partial<
  Omit<SettingsOut, "telegram_connected" | "warnings">
>;

export interface CityOut {
  name: string;
  name_ar: string;
}

export interface GovernorateOut {
  name: string;
  name_ar: string;
  cities: CityOut[];
}

export interface GeoOut {
  governorates: GovernorateOut[];
}

export interface KnowledgeFileOut {
  id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  char_count: number;
  status: string;
  error: string | null;
  preview: string | null;
  created_at: string;
}

export interface KnowledgeFileListOut {
  items: KnowledgeFileOut[];
  total: number;
}
