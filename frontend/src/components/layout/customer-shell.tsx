"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { Suspense, type ReactNode, useCallback, useEffect, useState } from "react";
import {
  Activity,
  BarChart3,
  Bell,
  Kanban,
  LayoutDashboard,
  LifeBuoy,
  LogOut,
  Menu,
  PanelLeft,
  PanelLeftClose,
  Send,
  Settings,
  Target,
  Users,
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
import { AUTH_ROUTES, CUSTOMER_ROUTES } from "@/config/routes";
import { useAuth } from "@/features/auth/auth-context";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

const CUSTOMER_NAV_ITEMS = [
  { label: "Dashboard", href: CUSTOMER_ROUTES.dashboard, icon: LayoutDashboard },
  { label: "ICP", href: CUSTOMER_ROUTES.icp, icon: Target },
  { label: "Leads", href: CUSTOMER_ROUTES.leads, icon: Users },
  { label: "Pipeline", href: CUSTOMER_ROUTES.pipeline, icon: Kanban },
  { label: "Outreach", href: CUSTOMER_ROUTES.outreach, icon: Send },
  { label: "Activity", href: CUSTOMER_ROUTES.activity, icon: Activity },
  { label: "Reports", href: CUSTOMER_ROUTES.reports, icon: BarChart3 },
  { label: "Support", href: CUSTOMER_ROUTES.support, icon: LifeBuoy },
  { label: "Settings", href: CUSTOMER_ROUTES.settings, icon: Settings },
] as const;

function CustomerNavLinks({
  collapsed = false,
  onNavigate,
  pendingOutreach = 0,
}: {
  collapsed?: boolean;
  onNavigate?: () => void;
  pendingOutreach?: number;
}) {
  const pathname = usePathname();

  return (
    <nav aria-label="Customer portal navigation" className="space-y-1">
      {CUSTOMER_NAV_ITEMS.map((item) => {
        const Icon = item.icon;
        const active = pathname === item.href || pathname.startsWith(`${item.href}/`);
        const showBadge = item.href === CUSTOMER_ROUTES.outreach && pendingOutreach > 0;
        const link = (
          <Link
            key={item.href}
            href={item.href}
            onClick={onNavigate}
            aria-label={collapsed ? item.label : undefined}
            className={cn(
              "relative flex items-center rounded-xl py-2.5 text-sm font-medium transition-all duration-200",
              collapsed ? "justify-center px-0" : "gap-3 px-3",
              active
                ? "bg-primary/12 font-semibold text-primary dark:bg-lime-500/15 dark:text-lime-300"
                : "text-muted-foreground hover:bg-surface-secondary hover:text-foreground",
            )}
          >
            <Icon className="size-4 shrink-0" />
            {!collapsed && <span className="flex-1 truncate">{item.label}</span>}
            {showBadge && !collapsed && (
              <Badge
                variant="secondary"
                className="ml-auto rounded-full bg-amber-500/20 px-1.5 py-0 text-[10px] font-bold text-amber-700 dark:text-amber-300"
              >
                {pendingOutreach}
              </Badge>
            )}
            {showBadge && collapsed && (
              <span className="absolute top-1.5 right-2 size-2 rounded-full bg-amber-500" />
            )}
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

export function CustomerShell({ children }: { children: ReactNode }) {
  const { user, tenant, logout } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [mobileOpen, setMobileOpen] = useState(false);
  const [collapsed, setCollapsed] = useState(false);
  const [pendingOutreach, setPendingOutreach] = useState(0);

  const refreshOutreachBadge = useCallback(async () => {
    try {
      const res = await api.get<{ total: number }>("/outreach/queue", {
        suppressUnauthorizedRedirect: true,
      });
      setPendingOutreach(res.total ?? 0);
    } catch {
      // Ignore badge fetch errors when offline or unauthenticated
    }
  }, []);

  useEffect(() => {
    let active = true;
    api
      .get<{ total: number }>("/outreach/queue", {
        suppressUnauthorizedRedirect: true,
      })
      .then((res) => {
        if (active) setPendingOutreach(res.total ?? 0);
      })
      .catch(() => {
        // Ignore badge fetch errors when offline or unauthenticated
      });
    return () => {
      active = false;
    };
  }, [pathname]);

  useEffect(() => {
    const handler = () => void refreshOutreachBadge();
    window.addEventListener("nexus:outreach-updated", handler);
    return () => window.removeEventListener("nexus:outreach-updated", handler);
  }, [refreshOutreachBadge]);

  async function handleLogout() {
    await logout();
    router.replace(AUTH_ROUTES.login);
  }

  return (
    <div className="flex min-h-screen bg-background text-foreground">
      {/* Desktop Collapsible Sidebar */}
      <aside
        className={cn(
          "hidden shrink-0 flex-col border-r border-border bg-surface/60 transition-[width] duration-300 ease-[cubic-bezier(0.22,1,0.36,1)] lg:flex",
          collapsed ? "w-[72px]" : "w-64",
        )}
      >
        <div
          className={cn(
            "flex h-16 items-center border-b border-border transition-all duration-300",
            collapsed ? "justify-center px-2" : "px-5",
          )}
        >
          <Logo compact={collapsed} />
        </div>
        <div className="flex-1 overflow-y-auto px-3 py-4">
          <Suspense fallback={null}>
            <CustomerNavLinks collapsed={collapsed} pendingOutreach={pendingOutreach} />
          </Suspense>
        </div>
        {tenant && !collapsed && (
          <div className="border-t border-border p-4">
            <p className="text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">Workspace</p>
            <p className="mt-1 truncate text-sm font-bold text-foreground">{tenant.name}</p>
            <p className="text-xs text-muted-foreground">{tenant.id}</p>
          </div>
        )}
      </aside>

      {/* Main Column */}
      <div className="flex min-w-0 flex-1 flex-col">
        {/* Top Header */}
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
                  <Button variant="ghost" size="icon" aria-label="Open navigation" className="lg:hidden">
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
                  <CustomerNavLinks onNavigate={() => setMobileOpen(false)} pendingOutreach={pendingOutreach} />
                </div>
              </SheetContent>
            </Sheet>

            {tenant && (
              <Badge variant="secondary" className="hidden border border-primary/20 bg-primary-light text-xs font-semibold text-emerald-dark sm:inline-flex dark:bg-surface-secondary dark:text-lime-300">
                {tenant.name}
              </Badge>
            )}
          </div>

          <div className="flex items-center gap-2">
            <Button variant="ghost" size="icon" aria-label="Notifications" className="rounded-full">
              <Bell className="size-4 text-muted-foreground" />
            </Button>

            <ThemeToggle />

            <DropdownMenu>
              <DropdownMenuTrigger
                render={
                  <Button variant="outline" className="h-9 rounded-full px-3 text-xs font-semibold">
                    <span className="max-w-[140px] truncate">{user?.fullName ?? "Account"}</span>
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

        {/* Main Content Area */}
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  );
}

