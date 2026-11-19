# NEXUS Frontend Architecture

## Overview
Built with **Next.js App Router**, **React 19**, **TypeScript**, and **Tailwind CSS v4** using a feature-oriented, modular architecture designed to scale from the public marketing landing page to the full multi-tenant AI SDR application.

## Folder Structure
- `src/app/(marketing)/`: Public marketing routes (`/` landing page) with its own layout.
- `src/app/(auth)/`: Placeholder route group for future Login / Register pages.
- `src/app/(application)/`: Placeholder route group for future Dashboard, Agents, Prospects, Leads, Pipeline, Analytics, and Settings pages.
- `src/components/ui/`: Generic UI primitives (shadcn/ui + Magic UI + Aceternity primitives).
- `src/components/shared/`: Cross-app reusable elements (`logo.tsx`, `theme-toggle.tsx`, `section-container.tsx`, `section-heading.tsx`, `shape-divider.tsx`).
- `src/components/layout/`: Navigation & Footer (`floating-navbar.tsx`, `mobile-navigation.tsx`, `footer.tsx`).
- `src/components/marketing/`: Independent landing page sections (`hero/`, `benefits/`, `problem/`, `workflow/`, `platform/`, `discovery/`, `metrics/`, `integrations/`, `comparison/`, `testimonials/`, `pricing/`, `faq/`, `cta/`).
- `src/components/effects/`: Thin wrappers for visual effects (`spotlight-background.tsx`, `geometric-pattern.tsx`, `animated-beam.tsx`, `browser-demo.tsx`).
- `src/features/`: Product-specific feature modules (`auth/`, `agents/`, `prospects/`, `leads/`, `enrichment/`, `outreach/`, `pipeline/`, `analytics/`, `integrations/`, `settings/`), ready for future implementation.
- `src/config/`: Site metadata, navigation links, theme, and design system constants.
- `src/lib/libraries/`: Integration wrappers for Motion, Icons, Shaders, Patterns, and Browser Window.
- `src/styles/tokens.css`: NEXUS Emerald Light/Dark design tokens.

## Architectural Rules
1. **Server Components by default**: Only interactive or browser/animation-dependent leaves use `"use client"`.
2. **Strict Separation**: `components/ui` contains zero business logic; `components/marketing` contains only public landing page sections; `features/` will hold authenticated product modules.
3. **Theme Support**: `next-themes` (`attribute="class"`) powers Light Mode (default) and Deep Emerald Dark Mode across all components.
4. **API Proxy**: `/api/*` is rewritten to `BACKEND_URL` in `next.config.ts` so cookies remain same-origin.

