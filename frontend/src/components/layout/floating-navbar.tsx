"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import {
  BarChart3,
  ChevronDown,
  Globe,
  HelpCircle,
  MessageSquare,
  Search,
  Send,
  ShieldCheck,
  Sparkles,
  Target,
  Users,
  Zap,
} from "lucide-react";
import { MobileNavigation } from "@/components/layout/mobile-navigation";
import { Logo } from "@/components/shared/logo";
import { ThemeToggle } from "@/components/shared/theme-toggle";
import { Button } from "@/components/ui/button";
import { navItems, type NavIconKey } from "@/config/navigation";
import { siteConfig } from "@/config/site";
import { cn } from "@/lib/utils";

const ICON_MAP: Record<NavIconKey, typeof Search> = {
  search: Search,
  sparkles: Sparkles,
  send: Send,
  barChart: BarChart3,
  users: Users,
  zap: Zap,
  target: Target,
  shield: ShieldCheck,
  message: MessageSquare,
  help: HelpCircle,
  globe: Globe,
};

export function FloatingNavbar() {
  const [openMenu, setOpenMenu] = useState<string | null>(null);
  const navContainerRef = useRef<HTMLDivElement>(null);

  const activeDropdown = navItems.find((item) => item.label === openMenu && item.items);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpenMenu(null);
    };
    const onPointerDown = (e: MouseEvent) => {
      if (navContainerRef.current && !navContainerRef.current.contains(e.target as Node)) {
        setOpenMenu(null);
      }
    };
    window.addEventListener("keydown", onKeyDown);
    document.addEventListener("mousedown", onPointerDown);
    return () => {
      window.removeEventListener("keydown", onKeyDown);
      document.removeEventListener("mousedown", onPointerDown);
    };
  }, []);

  return (
    <>
      {/* Full-viewport Backdrop Blur behind the Mega Menu when open */}
      {activeDropdown && (
        <div
          aria-hidden="true"
          onClick={() => setOpenMenu(null)}
          className="fixed inset-0 z-40 bg-black/25 backdrop-blur-md transition-opacity duration-200 dark:bg-black/45"
        />
      )}

      <header ref={navContainerRef} className="fixed inset-x-0 top-4 z-50 px-4">
        <nav
          aria-label="Primary navigation"
          className="mx-auto flex h-[68px] max-w-[1160px] items-center justify-between rounded-full border border-border/80 bg-white px-4 shadow-lg shadow-emerald-950/10 sm:px-6 dark:border-white/15 dark:bg-background/95"
        >
            <Logo />

            {/* Desktop Links */}
            <div className="hidden items-center gap-1 lg:flex">
              {navItems.map((item) =>
                item.items ? (
                  <button
                    key={item.label}
                    type="button"
                    aria-expanded={openMenu === item.label}
                    onClick={() => setOpenMenu((prev) => (prev === item.label ? null : item.label))}
                    className={cn(
                      "inline-flex cursor-pointer items-center gap-1 rounded-full px-3.5 py-2 text-sm font-medium transition-colors focus:outline-none",
                      openMenu === item.label
                        ? "bg-surface text-foreground"
                        : "text-foreground/85 hover:bg-surface hover:text-foreground",
                    )}
                  >
                    {item.label}
                    <ChevronDown
                      className={cn(
                        "size-3.5 opacity-70 transition-transform duration-200",
                        openMenu === item.label && "rotate-180",
                      )}
                    />
                  </button>
                ) : (
                  <Link
                    key={item.label}
                    href={item.href ?? "#"}
                    onClick={() => setOpenMenu(null)}
                    className="rounded-full px-3.5 py-2 text-sm font-medium text-foreground/85 transition-colors hover:bg-surface hover:text-foreground"
                  >
                    {item.label}
                  </Link>
                ),
              )}
            </div>

            {/* Desktop Actions */}
            <div className="hidden items-center gap-2.5 lg:flex">
              <ThemeToggle />
              <Button
                variant="ghost"
                className="rounded-full px-4 text-sm font-semibold"
                render={<Link href={siteConfig.links.login}>Log in</Link>}
              />
              <Button
                className="rounded-full bg-[rgb(203,248,115)] px-5 text-sm font-bold text-[#032219] transition-colors hover:bg-[rgb(190,240,95)]"
                render={<Link href={siteConfig.links.register}>Sign up</Link>}
              />
            </div>

            {/* Mobile Compact Menu */}
            <MobileNavigation />
          </nav>

        {/* Wide 2-Column Mega Menu Dropdown */}
        {activeDropdown && activeDropdown.items && (
          <div className="mx-auto mt-3 hidden max-w-[720px] lg:block">
            <div className="rounded-2xl border border-border/90 bg-card/95 p-6 shadow-2xl shadow-emerald-950/20 backdrop-blur-xl">
              <p className="mb-4 text-[11px] font-bold tracking-widest text-muted-foreground uppercase">
                {activeDropdown.label}
              </p>
              <div className="grid grid-cols-2 gap-3">
                {activeDropdown.items.map((sub) => {
                  const Icon = ICON_MAP[sub.icon];
                  return (
                    <Link
                      key={sub.label}
                      href={sub.href}
                      onClick={() => setOpenMenu(null)}
                      className="group flex items-start gap-3.5 rounded-xl p-3 transition-colors hover:bg-surface"
                    >
                      <span
                        className={cn(
                          "mt-0.5 flex size-10 shrink-0 items-center justify-center rounded-xl transition-transform group-hover:scale-105",
                          sub.iconColor,
                        )}
                      >
                        <Icon className="size-5" />
                      </span>
                      <div className="space-y-0.5">
                        <p className="text-sm font-semibold text-foreground">{sub.label}</p>
                        <p className="text-xs leading-relaxed text-muted-foreground">{sub.description}</p>
                      </div>
                    </Link>
                  );
                })}
              </div>
            </div>
          </div>
        )}
      </header>
    </>
  );
}
