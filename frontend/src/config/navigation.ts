export type NavIconKey =
  | "search"
  | "sparkles"
  | "send"
  | "barChart"
  | "users"
  | "zap"
  | "target"
  | "shield"
  | "message"
  | "help"
  | "globe";

export interface NavDropdownItem {
  label: string;
  description: string;
  href: string;
  icon: NavIconKey;
  iconColor: string;
}

export interface NavItem {
  label: string;
  href?: string;
  items?: NavDropdownItem[];
}

export const navItems: NavItem[] = [
  {
    label: "Platform",
    items: [
      {
        label: "AI Prospect Discovery",
        description: "Find high-fit B2B businesses across target cities and markets.",
        href: "#platform",
        icon: "search",
        iconColor: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
      },
      {
        label: "Lead Qualification",
        description: "Score and filter prospects against your Ideal Customer Profile.",
        href: "#workflow",
        icon: "sparkles",
        iconColor: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
      },
      {
        label: "Outreach & Approvals",
        description: "Personalized messaging with human-in-the-loop approval control.",
        href: "#integrations",
        icon: "send",
        iconColor: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
      },
      {
        label: "CRM Pipeline",
        description: "Track every qualified opportunity from first touch to closed deal.",
        href: "#platform",
        icon: "users",
        iconColor: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400",
      },
      {
        label: "WhatsApp & Telegram",
        description: "Engage leads on WhatsApp and escalate hot replies on Telegram.",
        href: "#integrations",
        icon: "message",
        iconColor: "bg-green-500/15 text-green-600 dark:text-green-400",
      },
      {
        label: "Cost & Funnel Analytics",
        description: "Monitor reply rates, win rates, and AI token costs in real time.",
        href: "#discovery",
        icon: "barChart",
        iconColor: "bg-rose-500/15 text-rose-600 dark:text-rose-400",
      },
    ],
  },
  {
    label: "Solutions",
    items: [
      {
        label: "Business Owners",
        description: "Build a predictable B2B pipeline without technical setup.",
        href: "#problem",
        icon: "target",
        iconColor: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
      },
      {
        label: "Sales Teams",
        description: "Focus on qualified opportunities and warm conversations.",
        href: "#problem",
        icon: "zap",
        iconColor: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
      },
      {
        label: "B2B Wholesalers",
        description: "Reach retail shops, clinics, and commercial buyers across regions.",
        href: "#discovery",
        icon: "globe",
        iconColor: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
      },
      {
        label: "Controlled Autonomy",
        description: "Start with assisted sending and scale safely to autopilot.",
        href: "#workflow",
        icon: "shield",
        iconColor: "bg-teal-500/15 text-teal-600 dark:text-teal-400",
      },
    ],
  },
  { label: "How It Works", href: "#workflow" },
  { label: "Pricing", href: "#pricing" },
  {
    label: "Resources",
    items: [
      {
        label: "FAQ",
        description: "Common questions about NEXUS and AI-assisted outreach.",
        href: "#faq",
        icon: "help",
        iconColor: "bg-emerald-500/15 text-emerald-600 dark:text-emerald-400",
      },
      {
        label: "Customer Stories",
        description: "See how B2B teams structure prospecting with NEXUS.",
        href: "#testimonials",
        icon: "users",
        iconColor: "bg-indigo-500/15 text-indigo-600 dark:text-indigo-400",
      },
      {
        label: "Integrations",
        description: "Connect WhatsApp, Telegram, CRM, and data sources.",
        href: "#integrations",
        icon: "zap",
        iconColor: "bg-amber-500/15 text-amber-600 dark:text-amber-400",
      },
      {
        label: "Workflow Guide",
        description: "Step-by-step look at how NEXUS turns goals into leads.",
        href: "#workflow",
        icon: "sparkles",
        iconColor: "bg-sky-500/15 text-sky-600 dark:text-sky-400",
      },
    ],
  },
];

export const footerColumns = [
  {
    title: "Product",
    links: [
      { label: "Platform", href: "#platform" },
      { label: "AI Agents", href: "#workflow" },
      { label: "Integrations", href: "#integrations" },
      { label: "Pricing", href: "#pricing" },
    ],
  },
  {
    title: "Solutions",
    links: [
      { label: "Business Owners", href: "#problem" },
      { label: "Sales Teams", href: "#problem" },
      { label: "B2B Companies", href: "#discovery" },
    ],
  },
  {
    title: "Resources",
    links: [
      { label: "Documentation", href: "#faq" },
      { label: "Guides", href: "#workflow" },
      { label: "Customer Stories", href: "#testimonials" },
      { label: "FAQ", href: "#faq" },
    ],
  },
  {
    title: "Company",
    links: [
      { label: "About Us", href: "#problem" },
      { label: "Contact", href: "#cta" },
      { label: "Privacy Policy", href: "#footer" },
      { label: "Terms of Service", href: "#footer" },
    ],
  },
] as const;
