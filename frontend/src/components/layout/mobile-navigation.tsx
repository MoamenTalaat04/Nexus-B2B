"use client";

import Link from "next/link";
import { Menu } from "lucide-react";
import { useState } from "react";
import { Logo } from "@/components/shared/logo";
import { ThemeToggle } from "@/components/shared/theme-toggle";
import { Button } from "@/components/ui/button";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { navItems } from "@/config/navigation";
import { siteConfig } from "@/config/site";

export function MobileNavigation() {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex items-center gap-2 lg:hidden">
      <ThemeToggle />
      <Sheet open={open} onOpenChange={setOpen}>
        <SheetTrigger
          render={
            <Button variant="ghost" size="icon" aria-label="Open menu" className="rounded-full">
              <Menu className="size-5" />
            </Button>
          }
        />
        <SheetContent side="right" className="w-[300px] border-border bg-background p-6">
          <SheetHeader className="mb-6 text-left">
            <SheetTitle>
              <Logo />
            </SheetTitle>
          </SheetHeader>
          <div className="flex flex-col gap-4">
            {navItems.map((item) =>
              item.items ? (
                <div key={item.label} className="space-y-2">
                  <p className="text-xs font-bold tracking-wider text-muted-foreground uppercase">{item.label}</p>
                  <div className="flex flex-col gap-1.5 pl-2">
                    {item.items.map((sub) => (
                      <Link
                        key={sub.label}
                        href={sub.href}
                        onClick={() => setOpen(false)}
                        className="rounded-md py-1 text-sm font-medium text-foreground transition-colors hover:text-primary"
                      >
                        {sub.label}
                      </Link>
                    ))}
                  </div>
                </div>
              ) : (
                <Link
                  key={item.label}
                  href={item.href ?? "#"}
                  onClick={() => setOpen(false)}
                  className="py-1 text-sm font-semibold text-foreground transition-colors hover:text-primary"
                >
                  {item.label}
                </Link>
              ),
            )}
            <div className="mt-4 flex flex-col gap-2.5 border-t border-border pt-4">
              <Button variant="outline" className="w-full rounded-full" render={<Link href={siteConfig.links.login} />}>
                Log in
              </Button>
              <Button
                className="w-full rounded-full bg-primary text-primary-foreground hover:bg-primary-hover"
                render={<Link href={siteConfig.links.register} />}
              >
                Sign up
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </div>
  );
}

