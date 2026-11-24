export interface LeadSummaryOut {
  id: string;
  ref_code: string;
  source: string;
  name: string;
  category: string | null;
  address: string | null;
  city: string | null;
  governorate: string | null;
  website: string | null;
  rating: number | null;
  reviews_count: number | null;
  status: string;
  score: number | null;
  score_reasons: string[];
  disqualify_reason: string | null;
  sourcing_run_id: string | null;
  agent_paused: boolean;
  created_at: string;
  updated_at: string;
}

export interface LeadListOut {
  items: LeadSummaryOut[];
  total: number;
  page: number;
  page_size: number;
}

export interface LeadStatsOut {
  total: number;
  by_status: Record<string, number>;
  avg_score: number | null;
  qualified_count: number;
  enriched_count: number;
  contacted_count: number;
  won_count: number;
}

export interface LeadContactOut {
  id: string;
  type: string;
  value: string;
  source: string;
  is_primary: boolean;
  confidence?: number;
}

export interface LeadNoteOut {
  id: string;
  body: string;
  author_user_id?: string | null;
  created_at: string;
}

export interface LeadMessageOut {
  id: string;
  direction: string;
  author: string;
  kind: string;
  purpose: string | null;
  status: string;
  body: string;
  template_name: string | null;
  reply_intent: string | null;
  redirected_to: string | null;
  error: string | null;
  sent_at: string | null;
  created_at: string;
}

export interface LeadHistoryOut {
  from_status: string | null;
  to_status: string;
  reason: string;
  actor: string;
  created_at: string;
}

export interface LeadOutcomeOut {
  outcome: "won" | "lost" | string;
  value_egp: number | null;
  reason: string | null;
  created_at: string;
}

export interface LeadDetailOut {
  id: string;
  ref_code?: string;
  name: string;
  category: string | null;
  address: string | null;
  city: string | null;
  governorate: string | null;
  website: string | null;
  google_maps_url: string | null;
  rating: number | null;
  reviews_count: number | null;
  status: string;
  score: number | null;
  score_reasons: string[];
  disqualify_reason: string | null;
  agent_paused: boolean;
  icp_version_id?: string | null;
  sourcing_run_id?: string | null;
  next_action_at?: string | null;
  first_contacted_at?: string | null;
  last_outbound_at?: string | null;
  last_inbound_at?: string | null;
  created_at?: string;
  window_expires_at?: string | null;
  contacts: LeadContactOut[];
  messages?: LeadMessageOut[];
  history?: LeadHistoryOut[];
  notes: LeadNoteOut[];
  outcome?: LeadOutcomeOut | null;
}

export interface RunOut {
  id: string;
  kind: string;
  status: "queued" | "running" | "succeeded" | "failed" | "cancelled";
  trigger: string;
  error: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cost_usd: number;
}

export interface RunListOut {
  items: RunOut[];
  total: number;
}

export interface StepOut {
  id: string;
  seq: number;
  step_type: string;
  name: string;
  input: unknown;
  output: unknown;
  model: string | null;
  input_tokens: number;
  output_tokens: number;
  cache_read_tokens: number;
  cost_usd: number;
  latency_ms: number;
  lead_id: string | null;
  created_at: string;
}

export interface RunDetailOut extends RunOut {
  input: Record<string, unknown>;
  output_summary: Record<string, unknown> | null;
  steps: StepOut[];
}
