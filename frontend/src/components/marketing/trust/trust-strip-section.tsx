import { Marquee } from "@/components/ui/marquee";
import { MotionReveal } from "@/lib/libraries/motion";

const PLACEHOLDER_BRANDS = [
  {
    name: "Northlane",
    tracking: "tracking-tight font-bold",
    symbol: (
      <svg viewBox="0 0 24 24" className="size-5 fill-none stroke-current" strokeWidth="2">
        <path d="M4 18V6l8 12V6" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M16 18V6l4 4" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    name: "Orbitra",
    tracking: "tracking-normal font-semibold",
    symbol: (
      <svg viewBox="0 0 24 24" className="size-5 fill-none stroke-current" strokeWidth="2">
        <circle cx="12" cy="12" r="4" />
        <ellipse cx="12" cy="12" rx="9" ry="4.5" transform="rotate(-24 12 12)" />
      </svg>
    ),
  },
  {
    name: "Asteron",
    tracking: "tracking-wide font-semibold uppercase text-sm",
    symbol: (
      <svg viewBox="0 0 24 24" className="size-5 fill-none stroke-current" strokeWidth="2">
        <path d="M12 3v18M4.2 7.5l15.6 9M19.8 7.5l-15.6 9" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    name: "Vellum",
    tracking: "tracking-tight font-extrabold",
    symbol: (
      <svg viewBox="0 0 24 24" className="size-5 fill-none stroke-current" strokeWidth="2.1">
        <path d="M5 6l7 12 7-12" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M9 6l3 5.5L15 6" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
  {
    name: "Novaflow",
    tracking: "tracking-normal font-bold",
    symbol: (
      <svg viewBox="0 0 24 24" className="size-5 fill-none stroke-current" strokeWidth="2">
        <path d="M4 14c2.5-4 5.5-4 8 0s5.5 4 8 0" strokeLinecap="round" />
        <path d="M4 9c2.5-4 5.5-4 8 0s5.5 4 8 0" strokeLinecap="round" />
      </svg>
    ),
  },
  {
    name: "Coreva",
    tracking: "tracking-tight font-semibold",
    symbol: (
      <svg viewBox="0 0 24 24" className="size-5 fill-none stroke-current" strokeWidth="2">
        <rect x="4" y="4" width="16" height="16" rx="4" />
        <circle cx="12" cy="12" r="3" />
      </svg>
    ),
  },
  {
    name: "Stratos",
    tracking: "tracking-wider font-bold uppercase text-sm",
    symbol: (
      <svg viewBox="0 0 24 24" className="size-5 fill-none stroke-current" strokeWidth="2">
        <path d="M4 16l8-10 8 10" strokeLinecap="round" strokeLinejoin="round" />
        <path d="M8 16l4-5 4 5" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    ),
  },
] as const;

export function TrustStripSection() {
  return (
    <section
      aria-label="Built for modern businesses"
      className="relative z-20 border-b border-border/70 bg-background py-10 md:py-14"
    >
      <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
        <MotionReveal className="flex flex-col items-center text-center">
          <p className="text-xs font-bold tracking-widest text-emerald-dark/80 uppercase dark:text-emerald-300/80">
            Built for modern businesses
          </p>
          <p className="mt-1.5 text-sm text-muted-foreground">
            Designed for teams that want to build better business connections.
          </p>

          <div className="relative mt-8 w-full overflow-hidden [mask-image:linear-gradient(to_right,transparent,black_10%,black_90%,transparent)]">
            <Marquee reverse pauseOnHover className="[--duration:26s] [--gap:3.5rem]">
              {PLACEHOLDER_BRANDS.map((brand) => (
                <div
                  key={brand.name}
                  className="flex h-10 shrink-0 items-center gap-2.5 text-foreground/60 transition-colors hover:text-emerald-dark dark:text-emerald-100/55 dark:hover:text-emerald-200"
                >
                  <span className="shrink-0">{brand.symbol}</span>
                  <span className={`text-base leading-none select-none ${brand.tracking}`}>{brand.name}</span>
                </div>
              ))}
            </Marquee>
          </div>
        </MotionReveal>
      </div>
    </section>
  );
}
