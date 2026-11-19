# NEXUS Component Registry

Every third-party UI component and visual effect used in NEXUS is tracked here.

## 1. UI Foundation — shadcn/ui
- **Library:** shadcn/ui (`base-nova` style)
- **Docs:** https://ui.shadcn.com/
- **License:** MIT (Free)
- **Installation:** `npx shadcn@latest add <component>`
- **Location:** `frontend/src/components/ui/`
- **Approved Components:**
  - `button.tsx`, `card.tsx`, `badge.tsx`, `accordion.tsx`, `sheet.tsx`, `separator.tsx`, `tooltip.tsx`, `dropdown-menu.tsx`, `navigation-menu.tsx`
- **Theme Compatibility:** Full Light & Dark mode via CSS variables.

## 2. Background Patterns & Effects — Magic UI
- **Library:** Magic UI
- **Docs:** https://magicui.design/docs/components
- **License:** MIT (Free Registry)
- **Installation:** `npx shadcn@latest add @magicui/<component>`
- **Location:** `frontend/src/components/ui/` (wrapped via `frontend/src/components/effects/`)
- **Approved Components:**
  1. `grid-pattern`: Hero and selected section backgrounds.
  2. `shine-border`: Selected highlighted cards (Comparison "With NEXUS", Featured Testimonial, Growth Pricing Card).
  3. `dotted-map`: Global Prospect Discovery section.
  4. `animated-theme-toggler`: Floating Navbar Light/Dark toggle.
  5. `animated-beam`: How NEXUS Works 4-step workflow & Integrations visualization.
  6. `aurora-text`: Hero "connections" emerald highlight word.
  7. `number-ticker`: Results & Metrics section.
  8. `safari`: Approved free replacement for React Bits Pro Browser Window in Hero & Platform Showcase.

## 3. Hero Spotlight — Aceternity UI (Free)
- **Library:** Aceternity UI
- **Docs:** https://ui.aceternity.com/components/spotlight
- **License:** Free (MIT / Open Source copy-paste registry)
- **Usage:** Approved free replacement for the Pro-gated Aceternity Spotlight Shader (`@aceternity/spotlight`), paired with Magic UI `GridPattern` over an Emerald Hero surface.
- **Location:** `frontend/src/components/effects/spotlight-background.tsx`

## 4. Animation System — Motion
- **Library:** `motion` (`motion/react`)
- **Docs:** https://motion.dev/
- **License:** MIT
- **Installation:** `npm install motion`
- **Location:** `frontend/src/lib/libraries/motion.ts`
- **Usage:** Entrance reveals, staggered cards, hover interactions, `useReducedMotion` support.

## 5. Icons — Lucide React
- **Library:** `lucide-react`
- **Docs:** https://lucide.dev/guide/react/
- **License:** ISC
- **Location:** `frontend/src/lib/libraries/icons.ts`
- **Usage:** Single icon library across the entire application.

