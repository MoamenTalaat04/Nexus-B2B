# NEXUS Design Tokens

## Color Palette

### Light Mode (Default)
| Token | Value | Usage |
|---|---|---|
| `--background` | `#FFFFFF` | Primary page background |
| `--foreground` | `#10231C` | Primary dark-green text & headings |
| `--surface` | `#F5F8F6` | Subtle section surfaces & card containers |
| `--surface-secondary` | `#EAF1ED` | Secondary highlighted surfaces |
| `--primary` | `#079669` | Emerald brand primary, CTAs, active states |
| `--primary-hover` | `#067D59` | Emerald hover state |
| `--primary-light` | `#DDF8EC` | Light emerald highlights & badges |
| `--emerald-dark` | `#073F30` | Deep emerald accents |
| `--emerald-deep` | `#052A20` | Footer & high-contrast dark emerald sections |
| `--border` | `#E2EAE5` | Subtle borders & dividers |
| `--muted` | `#64756C` | Muted body & secondary labels |

### Dark Mode (`.dark`)
| Token | Value | Usage |
|---|---|---|
| `--background` | `#061E19` | Deep emerald primary background |
| `--foreground` | `#F1F8F4` | Off-white / mint-tinted text |
| `--surface` | `#092D24` | Card & section surfaces |
| `--surface-secondary` | `#104535` | Secondary elevated surfaces |
| `--primary` | `#34D399` | Mint-emerald primary CTAs & highlights |
| `--primary-hover` | `#10B981` | Hover state |
| `--border` | `#1B5944` | Emerald-gray borders |
| `--muted` | `#A7BDB2` | Muted text |

## Typography
- **Font Family:** `Manrope` (loaded via `next/font/google`, CSS variable `--font-manrope`)
- **Weights:**
  - Hero Heading: `700`–`800`
  - Section Headings: `700`
  - Card Headings: `600`–`700`
  - Body Text: `400`–`500`
  - Navigation: `500`–`600`
  - Buttons: `600`

## Layout & Spacing
- **Max Content Width:** `1280px` (`max-w-7xl`)
- **Floating Navbar:** Centered pill container (`max-w-[1160px]`, `h-[72px]`, `rounded-full`)
- **Section Vertical Spacing:** `py-20 md:py-28` (`80px–112px`)
- **Border Radius:** Medium (`0.625rem` base, `rounded-xl` / `rounded-2xl` for cards)
- **Breakpoints:** Tailwind v4 defaults (`sm: 640px`, `md: 768px`, `lg: 1024px`, `xl: 1280px`)

