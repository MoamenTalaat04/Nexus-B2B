import { Check } from "lucide-react";
import { GeometricPattern } from "@/components/effects/geometric-pattern";
import { SectionContainer } from "@/components/shared/section-container";
import { AuroraText } from "@/components/ui/aurora-text";
import { MotionReveal } from "@/lib/libraries/motion";

function WhatsAppIcon() {
  return (
    <svg viewBox="0 0 48 48" className="size-12" aria-hidden="true">
      <rect width="48" height="48" rx="12" fill="#25D366" />
      <path
        fill="#FFFFFF"
        d="M24 10.5c-7.45 0-13.5 6.02-13.5 13.45 0 2.65.77 5.12 2.1 7.2l-1.37 5.02 5.14-1.35a13.48 13.48 0 0 0 7.63 2.36h.01c7.44 0 13.49-6.02 13.49-13.45 0-3.59-1.4-6.97-3.95-9.51A13.42 13.42 0 0 0 24 10.5Zm7.93 19.16c-.34.95-1.97 1.82-2.72 1.93-.7.11-1.58.15-2.55-.16-.59-.19-1.35-.44-2.32-.86-4.09-1.76-6.76-5.88-6.96-6.15-.2-.27-1.66-2.21-1.66-4.21 0-2 1.05-2.99 1.42-3.4.37-.4.81-.51 1.08-.51.27 0 .54 0 .77.01.25.01.58-.09.91.7.34.81 1.15 2.8 1.25 3 .1.2.17.44.03.71-.13.27-.2.44-.4.67-.2.24-.42.53-.6.71-.2.2-.41.42-.18.82.24.4 1.05 1.73 2.25 2.8 1.55 1.38 2.85 1.81 3.25 2.01.4.2.64.17.88-.1.24-.27 1.01-1.18 1.28-1.58.27-.4.54-.34.91-.2.37.13 2.36 1.11 2.76 1.31.4.2.67.3.77.47.1.17.1.98-.24 1.93Z"
      />
    </svg>
  );
}

function TelegramIcon() {
  return (
    <svg viewBox="0 0 48 48" className="size-12" aria-hidden="true">
      <defs>
        <linearGradient id="tg-grad" x1="24" y1="0" x2="24" y2="48" gradientUnits="userSpaceOnUse">
          <stop offset="0%" stopColor="#37AEE2" />
          <stop offset="100%" stopColor="#1E96C8" />
        </linearGradient>
      </defs>
      <rect width="48" height="48" rx="12" fill="url(#tg-grad)" />
      <path
        fill="#FFFFFF"
        d="M34.95 14.37 12.68 22.96c-1.52.61-1.51 1.46-.28 1.84l5.72 1.78 13.23-8.35c.62-.38 1.2-.17.73.24L21.36 28.15l-.4 5.93c.58 0 .84-.27 1.17-.58l2.8-2.72 5.82 4.3c1.07.59 1.84.29 2.11-.99l3.82-18c.39-1.56-.6-2.27-1.73-1.72Z"
      />
    </svg>
  );
}

function SalesforceIcon() {
  return (
    <svg viewBox="0 0 48 48" className="size-12" aria-hidden="true">
      <path
        fill="#00A1E0"
        d="M19.86 13.4c1.66-1.73 3.98-2.8 6.55-2.8 3.63 0 6.76 2.13 8.21 5.21a8.2 8.2 0 0 1 3.18-.64c4.53 0 8.2 3.7 8.2 8.27 0 4.56-3.67 8.26-8.2 8.26-.63 0-1.25-.07-1.84-.21a6.44 6.44 0 0 1-5.68 3.41c-1.1 0-2.13-.27-3.04-.75a7.48 7.48 0 0 1-6.52 3.85c-3.57 0-6.55-2.52-7.27-5.89-.46.1-.94.15-1.43.15C7.82 32.26 4 28.4 4 23.64c0-3.82 2.47-7.06 5.88-8.19a8.76 8.76 0 0 1 9.98-2.05Z"
      />
      <text
        x="25"
        y="26.5"
        textAnchor="middle"
        fill="#FFFFFF"
        fontSize="7.4"
        fontWeight="700"
        fontFamily="system-ui, -apple-system, sans-serif"
      >
        salesforce
      </text>
    </svg>
  );
}

function GooglePlacesIcon() {
  return (
    <svg viewBox="0 0 48 48" className="size-12" aria-hidden="true">
      <path
        fill="#1A73E8"
        d="M28.6 9.1A12.4 12.4 0 0 0 14.3 13l5.3 4.5a6 6 0 0 1 6.7-1.9l2.3-6.5Z"
      />
      <path
        fill="#EA4335"
        d="M14.3 13A12.4 12.4 0 0 0 11.6 21c0 2.5.7 4.7 1.9 6.6l6.1-5.1a5.9 5.9 0 0 1-.8-2.9c0-.8.2-1.5.8-2.1L14.3 13Z"
      />
      <path
        fill="#FBBC04"
        d="M13.5 27.6c1.5 2.4 3.4 4.5 5 6.8l7.2-6a5.9 5.9 0 0 1-6.1-5.9l-6.1 5.1Z"
      />
      <path
        fill="#34A853"
        d="M18.5 34.4c1.9 2.7 3.7 5.7 4.6 8.9.2.7 1.6.7 1.8 0 1-3.3 3-6.5 5.1-9.4 2.5-3.4 6.4-7.4 6.4-12.9 0-2.5-.7-4.8-2-6.8l-8.7 7.3a6 6 0 0 1-7.2 5.9l-0 7Z"
      />
      <path
        fill="#4285F4"
        d="M28.6 9.1c2.6.8 4.8 2.6 5.8 5.1l-8.7 7.3a5.9 5.9 0 0 0 .6-6l2.3-6.4Z"
      />
      <circle cx="24" cy="21" r="4.6" fill="#FFFFFF" />
    </svg>
  );
}

function GmailIcon() {
  return (
    <svg viewBox="0 0 48 48" className="size-12" aria-hidden="true">
      <path fill="#4285F4" d="M8 15.5V35c0 1.4 1.1 2.5 2.5 2.5H15V22.4L8 15.5Z" />
      <path fill="#34A853" d="M40 15.5V35c0 1.4-1.1 2.5-2.5 2.5H33V22.4l7-6.9Z" />
      <path fill="#FBBC04" d="M33 13v9.4l7-6.9v-2.1c0-2.7-3.1-4.2-5.2-2.5L33 13Z" />
      <path fill="#EA4335" d="M15 22.4V13l9 6.8 9-6.8v9.4l-9 6.8-9-6.8Z" />
      <path fill="#C5221F" d="M8 13.4v2.1l7 6.9V13l-1.8-2.1C11.1 9.2 8 10.7 8 13.4Z" />
    </svg>
  );
}

const INTEGRATIONS = [
  { name: "WhatsApp", category: "Messaging", Icon: WhatsAppIcon },
  { name: "Telegram", category: "Owner Alerts", Icon: TelegramIcon },
  { name: "CRM Pipeline", category: "Lead Sync", Icon: SalesforceIcon },
  { name: "Google Places", category: "Discovery", Icon: GooglePlacesIcon },
  { name: "Email", category: "Enrichment", Icon: GmailIcon },
] as const;

export function IntegrationsSection() {
  return (
    <SectionContainer id="integrations" className="bg-surface/60">
      <GeometricPattern variant="dots-corners" />

      <div className="mx-auto max-w-2xl space-y-3 text-center">
        <h2 className="text-[clamp(1.75rem,3vw,2.5rem)] leading-[1.15] font-bold tracking-tight text-foreground">
          Connect{" "}
          <AuroraText
            colors={["#079669", "#65A30D", "#84CC16", "#10B981"]}
            speed={1.2}
            className="font-extrabold"
          >
            NEXUS
          </AuroraText>{" "}
          to your existing workflow.
        </h2>

        <p className="text-base leading-relaxed text-muted-foreground md:text-lg">
          Work with the messaging and data channels your team already relies on.
        </p>
      </div>

      <MotionReveal className="mt-12 grid grid-cols-2 gap-4 sm:grid-cols-3 md:grid-cols-5">
        {INTEGRATIONS.map(({ name, category, Icon }) => (
          <div
            key={name}
            className="relative flex flex-col items-center justify-center overflow-hidden rounded-2xl border border-border/80 bg-card px-5 py-7 text-center transition-all duration-200 hover:-translate-y-0.5 hover:border-primary/40"
          >
            <div className="relative z-10 flex flex-col items-center">
              <div className="mb-4 flex size-14 items-center justify-center">
                <Icon />
              </div>

              <p className="text-sm font-bold text-foreground sm:text-base">{name}</p>
              <p className="mt-0.5 text-xs text-muted-foreground">{category}</p>

              <span className="mt-4 inline-flex items-center gap-1.5 rounded-full border border-emerald-200/80 bg-emerald-50/90 px-3 py-1 text-[11px] font-semibold text-emerald-700 dark:border-emerald-500/25 dark:bg-emerald-950/60 dark:text-emerald-300">
                <span className="flex size-3.5 items-center justify-center rounded-full bg-emerald-600 text-white dark:bg-emerald-500">
                  <Check className="size-2.5" strokeWidth={3} />
                </span>
                Integrated
              </span>
            </div>
          </div>
        ))}
      </MotionReveal>
    </SectionContainer>
  );
}
