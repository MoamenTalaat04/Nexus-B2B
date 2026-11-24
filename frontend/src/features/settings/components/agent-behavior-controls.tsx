"use client";

import {
  Bot,
  Briefcase,
  Hand,
  ShieldCheck,
  Smile,
  UserCheck,
  Zap,
  type LucideIcon,
} from "lucide-react";
import { Label } from "@/components/ui/label";
import type { AutonomyMode, FirstTouchMode } from "@/lib/types";
import { cn } from "@/lib/utils";

export interface DialectOption {
  code: string;
  label: string;
}

export interface LanguageGroup {
  code: string;
  label: string;
  dialects: DialectOption[];
}

export const LANGUAGE_CATALOG: LanguageGroup[] = [
  {
    code: "ar",
    label: "Arabic (العربية)",
    dialects: [
      { code: "ar-EG", label: "Egypt (مصري)" },
      { code: "ar-SA", label: "Saudi Arabia (سعودي)" },
      { code: "ar-AE", label: "UAE (إماراتي)" },
      { code: "ar-KW", label: "Kuwait (كويتي)" },
      { code: "ar-QA", label: "Qatar (قطري)" },
      { code: "ar-BH", label: "Bahrain (بحريني)" },
      { code: "ar-OM", label: "Oman (عُماني)" },
      { code: "ar-JO", label: "Jordan (أردني)" },
      { code: "ar-LB", label: "Lebanon (لبناني)" },
      { code: "ar-MA", label: "Morocco (مغربي)" },
      { code: "ar-DZ", label: "Algeria (جزائري)" },
      { code: "ar-TN", label: "Tunisia (تونسي)" },
      { code: "ar-IQ", label: "Iraq (عراقي)" },
      { code: "ar", label: "Modern Standard Arabic (الفصحى)" },
    ],
  },
  {
    code: "en",
    label: "English",
    dialects: [
      { code: "en-US", label: "United States (American)" },
      { code: "en-GB", label: "United Kingdom (British)" },
      { code: "en-CA", label: "Canada" },
      { code: "en-AU", label: "Australia" },
      { code: "en-IE", label: "Ireland" },
      { code: "en-NZ", label: "New Zealand" },
      { code: "en-ZA", label: "South Africa" },
      { code: "en-SG", label: "Singapore" },
      { code: "en", label: "International / Neutral" },
    ],
  },
  {
    code: "fr",
    label: "French (Français)",
    dialects: [
      { code: "fr-FR", label: "France" },
      { code: "fr-CA", label: "Canada (Québec)" },
      { code: "fr-BE", label: "Belgium" },
      { code: "fr-CH", label: "Switzerland" },
      { code: "fr-MA", label: "North / West Africa" },
    ],
  },
  {
    code: "es",
    label: "Spanish (Español)",
    dialects: [
      { code: "es-ES", label: "Spain" },
      { code: "es-MX", label: "Mexico" },
      { code: "es-419", label: "Latin America" },
      { code: "es-AR", label: "Argentina" },
      { code: "es-CO", label: "Colombia" },
      { code: "es-CL", label: "Chile" },
      { code: "es-US", label: "United States" },
    ],
  },
  {
    code: "pt",
    label: "Portuguese (Português)",
    dialects: [
      { code: "pt-BR", label: "Brazil" },
      { code: "pt-PT", label: "Portugal" },
    ],
  },
  {
    code: "de",
    label: "German (Deutsch)",
    dialects: [
      { code: "de-DE", label: "Germany" },
      { code: "de-AT", label: "Austria" },
      { code: "de-CH", label: "Switzerland" },
    ],
  },
  {
    code: "it",
    label: "Italian (Italiano)",
    dialects: [
      { code: "it-IT", label: "Italy" },
      { code: "it-CH", label: "Switzerland" },
    ],
  },
  {
    code: "nl",
    label: "Dutch (Nederlands)",
    dialects: [
      { code: "nl-NL", label: "Netherlands" },
      { code: "nl-BE", label: "Belgium (Flemish)" },
    ],
  },
  {
    code: "tr",
    label: "Turkish (Türkçe)",
    dialects: [{ code: "tr-TR", label: "Turkey" }],
  },
  {
    code: "ru",
    label: "Russian (Русский)",
    dialects: [{ code: "ru-RU", label: "Russia" }],
  },
  {
    code: "zh",
    label: "Chinese (中文)",
    dialects: [
      { code: "zh-CN", label: "Mainland China (Simplified)" },
      { code: "zh-TW", label: "Taiwan (Traditional)" },
      { code: "zh-HK", label: "Hong Kong" },
    ],
  },
  {
    code: "ja",
    label: "Japanese (日本語)",
    dialects: [{ code: "ja-JP", label: "Japan" }],
  },
  {
    code: "ko",
    label: "Korean (한국어)",
    dialects: [{ code: "ko-KR", label: "South Korea" }],
  },
  {
    code: "hi",
    label: "Hindi (हिन्दी)",
    dialects: [{ code: "hi-IN", label: "India" }],
  },
  {
    code: "ur",
    label: "Urdu (اردو)",
    dialects: [{ code: "ur-PK", label: "Pakistan" }],
  },
  {
    code: "id",
    label: "Indonesian (Bahasa Indonesia)",
    dialects: [{ code: "id-ID", label: "Indonesia" }],
  },
  {
    code: "ms",
    label: "Malay (Bahasa Melayu)",
    dialects: [{ code: "ms-MY", label: "Malaysia" }],
  },
  {
    code: "pl",
    label: "Polish (Polski)",
    dialects: [{ code: "pl-PL", label: "Poland" }],
  },
  {
    code: "sv",
    label: "Swedish (Svenska)",
    dialects: [{ code: "sv-SE", label: "Sweden" }],
  },
  {
    code: "nb",
    label: "Norwegian (Norsk)",
    dialects: [{ code: "nb-NO", label: "Norway" }],
  },
  {
    code: "da",
    label: "Danish (Dansk)",
    dialects: [{ code: "da-DK", label: "Denmark" }],
  },
  {
    code: "fi",
    label: "Finnish (Suomi)",
    dialects: [{ code: "fi-FI", label: "Finland" }],
  },
  {
    code: "el",
    label: "Greek (Ελληνικά)",
    dialects: [{ code: "el-GR", label: "Greece" }],
  },
  {
    code: "he",
    label: "Hebrew (עברית)",
    dialects: [{ code: "he-IL", label: "Israel" }],
  },
  {
    code: "fa",
    label: "Persian (فارسی)",
    dialects: [{ code: "fa-IR", label: "Iran" }],
  },
  {
    code: "th",
    label: "Thai (ไทย)",
    dialects: [{ code: "th-TH", label: "Thailand" }],
  },
  {
    code: "vi",
    label: "Vietnamese (Tiếng Việt)",
    dialects: [{ code: "vi-VN", label: "Vietnam" }],
  },
  {
    code: "uk",
    label: "Ukrainian (Українська)",
    dialects: [{ code: "uk-UA", label: "Ukraine" }],
  },
  {
    code: "ro",
    label: "Romanian (Română)",
    dialects: [{ code: "ro-RO", label: "Romania" }],
  },
  {
    code: "cs",
    label: "Czech (Čeština)",
    dialects: [{ code: "cs-CZ", label: "Czechia" }],
  },
  {
    code: "hu",
    label: "Hungarian (Magyar)",
    dialects: [{ code: "hu-HU", label: "Hungary" }],
  },
];

function resolveLanguageGroup(value: string): LanguageGroup {
  const normalized = value.trim().toLowerCase();
  const exactDialect = LANGUAGE_CATALOG.find((g) =>
    g.dialects.some((d) => d.code.toLowerCase() === normalized),
  );
  if (exactDialect) return exactDialect;

  const base = normalized.split("-")[0];
  return LANGUAGE_CATALOG.find((g) => g.code === base) ?? LANGUAGE_CATALOG[0];
}

export function LanguageDialectSelector({
  value,
  onChange,
  idPrefix = "agent",
}: {
  value: string;
  onChange: (nextCode: string) => void;
  idPrefix?: string;
}) {
  const group = resolveLanguageGroup(value);
  const dialectExists = group.dialects.some((d) => d.code.toLowerCase() === value.trim().toLowerCase());
  const selectedDialect = dialectExists ? value : group.dialects[0].code;

  return (
    <div className="grid gap-4 sm:grid-cols-2">
      <div className="grid gap-1.5">
        <Label htmlFor={`${idPrefix}-lang`}>Outreach language</Label>
        <select
          id={`${idPrefix}-lang`}
          value={group.code}
          onChange={(e) => {
            const nextGroup = LANGUAGE_CATALOG.find((g) => g.code === e.target.value) ?? LANGUAGE_CATALOG[0];
            onChange(nextGroup.dialects[0].code);
          }}
          className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm text-foreground dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white"
        >
          {LANGUAGE_CATALOG.map((lang) => (
            <option key={lang.code} value={lang.code}>
              {lang.label}
            </option>
          ))}
        </select>
      </div>

      <div className="grid gap-1.5">
        <Label htmlFor={`${idPrefix}-dialect`}>Dialect / Regional variant</Label>
        <select
          id={`${idPrefix}-dialect`}
          value={selectedDialect}
          onChange={(e) => onChange(e.target.value)}
          className="h-10 rounded-lg border border-input bg-surface/70 px-3 text-sm text-foreground dark:border-[#223D27] dark:bg-[#0A140C] dark:text-white"
        >
          {group.dialects.map((dialect) => (
            <option key={dialect.code} value={dialect.code}>
              {dialect.label}
            </option>
          ))}
        </select>
      </div>
    </div>
  );
}

interface CardOption<T extends string> {
  value: T;
  title: string;
  description: string;
  icon: LucideIcon;
}

function BehaviorCardGroup<T extends string>({
  label,
  value,
  options,
  columnsClass,
  onChange,
}: {
  label: string;
  value: T;
  options: CardOption<T>[];
  columnsClass: string;
  onChange: (next: T) => void;
}) {
  return (
    <div className="space-y-2">
      <Label>{label}</Label>
      <div className={cn("grid gap-2.5", columnsClass)}>
        {options.map((opt) => {
          const Icon = opt.icon;
          const active = value === opt.value;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => onChange(opt.value)}
              className={cn(
                "flex items-start gap-3 rounded-xl border p-3 text-left transition-all",
                active
                  ? "border-primary bg-primary/10 shadow-xs dark:border-lime-400 dark:bg-lime-500/15"
                  : "border-border/80 bg-surface/50 hover:border-primary/45 dark:border-[#223D27] dark:bg-[#0A140C]/60 dark:hover:border-lime-400/45",
              )}
            >
              <span
                className={cn(
                  "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-lg border transition-colors",
                  active
                    ? "border-primary/40 bg-primary text-primary-foreground dark:border-lime-400/50 dark:bg-lime-400 dark:text-[#0A140C]"
                    : "border-border/80 bg-card text-muted-foreground dark:border-[#223D27] dark:bg-[#112014]",
                )}
              >
                <Icon className="size-4" />
              </span>
              <span className="min-w-0">
                <span className="block text-xs font-semibold text-foreground">{opt.title}</span>
                <span className="mt-0.5 block text-[11px] leading-snug text-muted-foreground">
                  {opt.description}
                </span>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}

const TONE_OPTIONS: CardOption<"friendly" | "formal">[] = [
  {
    value: "friendly",
    title: "Friendly",
    description: "Warm, natural, and conversational.",
    icon: Smile,
  },
  {
    value: "formal",
    title: "Formal",
    description: "Polite, structured, and executive-ready.",
    icon: Briefcase,
  },
];

const AUTONOMY_OPTIONS: CardOption<AutonomyMode>[] = [
  {
    value: "approve_all",
    title: "Approve All",
    description: "Every message waits for your approval first.",
    icon: ShieldCheck,
  },
  {
    value: "approve_first_touch",
    title: "Approve First Touch",
    description: "Approve openers only; follow-ups send automatically.",
    icon: UserCheck,
  },
  {
    value: "autopilot",
    title: "Autopilot",
    description: "Sends automatically within daily cap & hours.",
    icon: Zap,
  },
];

const FIRST_TOUCH_OPTIONS: CardOption<FirstTouchMode>[] = [
  {
    value: "assisted",
    title: "Assisted",
    description: "AI writes the opener; you send it personally.",
    icon: Hand,
  },
  {
    value: "api_template",
    title: "API Template",
    description: "Sends approved WhatsApp API templates automatically.",
    icon: Bot,
  },
];

export function ToneCardsSelector({
  value,
  onChange,
}: {
  value: "friendly" | "formal";
  onChange: (next: "friendly" | "formal") => void;
}) {
  return (
    <BehaviorCardGroup
      label="Tone"
      value={value}
      options={TONE_OPTIONS}
      columnsClass="sm:grid-cols-2"
      onChange={onChange}
    />
  );
}

export function AutonomyModeCardsSelector({
  value,
  onChange,
}: {
  value: AutonomyMode;
  onChange: (next: AutonomyMode) => void;
}) {
  return (
    <BehaviorCardGroup
      label="Autonomy mode"
      value={value}
      options={AUTONOMY_OPTIONS}
      columnsClass="sm:grid-cols-3"
      onChange={onChange}
    />
  );
}

export function FirstTouchModeCardsSelector({
  value,
  onChange,
}: {
  value: FirstTouchMode;
  onChange: (next: FirstTouchMode) => void;
}) {
  return (
    <BehaviorCardGroup
      label="First-touch mode"
      value={value}
      options={FIRST_TOUCH_OPTIONS}
      columnsClass="sm:grid-cols-2"
      onChange={onChange}
    />
  );
}
