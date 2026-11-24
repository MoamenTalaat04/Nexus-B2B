"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, type ReactNode, useState } from "react";
import {
  Building2,
  Cpu,
  CreditCard,
  Globe,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  Menu,
  Package,
  PanelLeft,
  PanelLeftClose,
  ShieldCheck,
  UserCog,
} from "lucide-react";
import { Logo } from "@/components/shared/logo";
import { ThemeToggle } from "@/components/shared/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip";
import { ADMIN_ROUTES, AUTH_ROUTES } from "@/config/routes";
import { useAuth } from "@/features/auth/auth-context";
import { cn } from "@/lib/utils";

const ADMIN_NAV_ITEMS = [
  { label: "Dashboard", href: ADMIN_ROUTES.dashboard, icon: LayoutDashboard, superAdminOnly: false },
  { label: "Customers", href: ADMIN_ROUTES.customers, icon: Building2, superAdminOnly: false },
  { label: "Admins", href: ADMIN_ROUTES.admins, icon: UserCog, superAdminOnly: true },
  { label: "Plans", href: ADMIN_ROUTES.plans, icon: Package, superAdminOnly: false },
  { label: "Billing", href: ADMIN_ROUTES.billing, icon: CreditCard, superAdminOnly: true },
  { label: "LLM Providers", href: ADMIN_ROUTES.llmProviders, icon: Cpu, superAdminOnly: true },
  { label: "Search Sources", href: ADMIN_ROUTES.searchSources, icon: Globe, superAdminOnly: true },
  { label: "Support", href: ADMIN_ROUTES.support, icon: LifeBuoy, superAdminOnly: false },
  { label: "Security", href: ADMIN_ROUTES.security, icon: ShieldCheck, superAdminOnly: false },
] as const;

function AdminNavLinks({
  collapsed = false,
  onNavigate,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
}) {
  const pathname = usePathname();
  const { user } = useAuth();
  const isSuperAdmin = user?.role === "super_admin";

  const visibleItems = ADMIN_NAV_ITEMS.filter((item) => !item.superAdminOnly || isSuperAdmin);

  return (
    <nav aria-label="Platform admin navigation" className="space-y-1">
      {visibleItems.map((item) => {
        const Icon = item.icon;
        const active =
          item.href === "/admin"
            ? pathname === "/admin"
            : pathname === item.href || pathname.startsWith(`${item.href}/`);
        const link = (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-label={collapsed ? item.label : undefined}
            className={cn(
              "flex items-center rounded-xl py-2.5 text-sm font-medium transition-all duration-200",
              collapsed ? "justify-center px-0" : "gap-3 px-3",
              active
                ? "bg-primary/12 font-semibold text-primary dark:bg-lime-500/15 dark:text-lime-300"
                : "text-muted-foreground hover:bg-surface-secondary hover:text-foreground",
            )}
          >
            <Icon className="size-4 shrink-0" />
            {!collapsed && <span className="truncate">{item.label}</span>}
          </Link>
        );

        if (!collapsed) return link;

        return (
          <Tooltip key={item.href}>
            <TooltipTrigger render={link} />
            <TooltipContent side="right" sideOffset={10}>
              {item.label}
            </TooltipContent>
          </Tooltip>
        );
      })}
    </nav>
  );
}

export function AdminShell({ children }: { children: ReactNode }) {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);

  async function handleLogout() {
    await logout();
    router.replace(AUTH_ROUTES.login);
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* Desktop Collapsible Admin Sidebar */}
      <aside
        className={cn(
          "hidden shrink-0 flex-col border-r border-border bg-surface/80 transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] lg:flex",
          collapsed ? "w-[72px]" : "w-64",
        )}
      >
        <div
          className={cn(
            "flex h-16 items-center border-b border-border transition-all duration-300",
            collapsed ? "justify-center px-2" : "justify-between px-5",
          )}
        >
          <Logo compact={collapsed} />
          {!collapsed && (
            <Badge variant="outline" className="border-primary/30 text-[10px] font-bold text-primary uppercase">
              Admin
            </Badge>
          )}
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-4">
          <Suspense fallback={null}>
            <AdminNavLinks collapsed={collapsed} />
          </Suspense>
        </div>
        {!collapsed && (
          <div className="border-t border-border p-4">
            <div className="flex items-center gap-2 text-xs font-semibold text-foreground">
              <ShieldCheck className="size-4 text-primary" />
              <span>{user?.role === "super_admin" ? "Super Admin" : "Platform Admin"}</span>
            </div>
            <p className="mt-1 truncate text-xs text-muted-foreground">{user?.email}</p>
          </div>
        )}
      </aside>

      {/* Main Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b border-border bg-background/90 px-4 backdrop-blur-md sm:px-6">
          <div className="flex items-center gap-3">
            <Button
              variant="ghost"
              size="icon"
              onClick={() => setCollapsed((prev) => !prev)}
              aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
              className="hidden size-9 rounded-lg text-muted-foreground hover:text-foreground lg:inline-flex"
            >
              {collapsed ? <PanelLeft className="size-4" /> : <PanelLeftClose className="size-4" />}
            </Button>
            <Sheet open={mobileOpen} onOpenChange={setMobileOpen}>
              <SheetTrigger
                render={
                  <Button variant="ghost" size="icon" aria-label="Open admin navigation" className="lg:hidden">
                    <Menu className="size-5" />
                  </Button>
                }
              />
              <SheetContent side="left" className="w-64 p-0">
                <SheetHeader className="border-b border-border px-5 py-4 text-left">
                  <SheetTitle>
                    <Logo />
                  </SheetTitle>
                </SheetHeader>
                <div className="p-3">
                  <AdminNavLinks onNavigate={() => setMobileOpen(false)} />
                </div>
              </SheetContent>
            </Sheet>

            <Badge className="bg-primary/15 text-xs font-semibold text-primary dark:text-lime-300">
              Platform Admin Portal
            </Badge>
          </div>

          <div className="flex items-center gap-2">
            <ThemeToggle />

            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button variant="outline" className="h-9 rounded-full px-3 text-xs font-semibold">
                    <span className="max-w-[140px] truncate">{user?.fullName ?? "Admin"}</span>
                  </Button>
                }
              />
              <DropdownMenuContent align="end" className="w-56">
                <DropdownMenuLabel>
                  <p className="truncate text-sm font-semibold text-foreground">{user?.fullName}</p>
                  <p className="truncate text-xs font-normal text-muted-foreground">{user?.email}</p>
                  <p className="mt-1 text-[11px] font-semibold text-primary">{user?.role}</p>
                </DropdownMenuLabel>
                <DropdownMenuSeparator />
                <DropdownMenuItem onClick={handleLogout} className="cursor-pointer text-destructive focus:text-destructive">
                  <LogOut className="mr-2 size-4" />
                  Log out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>

            <Button
              variant="ghost"
              size="sm"
              onClick={handleLogout}
              className="h-9 gap-1.5 rounded-full px-3 text-xs font-semibold text-muted-foreground hover:bg-destructive/10 hover:text-destructive"
            >
              <LogOut className="size-3.5" />
              <span className="hidden sm:inline">Log out</span>
            </Button>
          </div>
        </header>

        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}

