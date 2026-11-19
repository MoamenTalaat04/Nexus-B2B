import Link from "next/link";
import { Logo } from "@/components/shared/logo";
import { footerColumns } from "@/config/navigation";
import { siteConfig } from "@/config/site";

export function Footer() {
  return (
    <footer
      id="footer"
      className="border-t border-border bg-surface/80 text-foreground dark:border-[#223D27] dark:bg-[#070E08] dark:text-lime-50"
    >
      <div className="mx-auto max-w-7xl px-4 py-16 sm:px-6 lg:px-8">
        <div className="grid gap-12 lg:grid-cols-6">
          <div className="space-y-4 lg:col-span-2">
            <Logo />
            <p className="max-w-xs text-sm leading-relaxed text-muted-foreground dark:text-lime-100/75">
              {siteConfig.tagline}
            </p>
            <div className="flex items-center gap-3 pt-1 text-xs font-medium text-muted-foreground dark:text-lime-200/70">
              <Link href="#footer" className="transition-colors hover:text-foreground dark:hover:text-white">
                LinkedIn
              </Link>
              <span>·</span>
              <Link href="#footer" className="transition-colors hover:text-foreground dark:hover:text-white">
                X / Twitter
              </Link>
              <span>·</span>
              <Link href="#footer" className="transition-colors hover:text-foreground dark:hover:text-white">
                GitHub
              </Link>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-8 sm:grid-cols-4 lg:col-span-4">
            {footerColumns.map((col) => (
              <div key={col.title} className="space-y-3">
                <h3 className="text-xs font-bold tracking-wider text-primary uppercase dark:text-lime-300">
                  {col.title}
                </h3>
                <ul className="space-y-2.5 text-sm">
                  {col.links.map((link) => (
                    <li key={link.label}>
                      <Link
                        href={link.href}
                        className="text-muted-foreground transition-colors hover:text-foreground dark:text-lime-100/75 dark:hover:text-white"
                      >
                        {link.label}
                      </Link>
                    </li>
                  ))}
                </ul>
              </div>
            ))}
          </div>
        </div>

        <div className="mt-12 flex flex-col items-center justify-between gap-4 border-t border-border pt-8 text-xs text-muted-foreground sm:flex-row dark:border-[#223D27] dark:text-lime-200/65">
          <p>© 2026 {siteConfig.name}. All rights reserved.</p>
          <div className="flex items-center gap-6">
            <Link href="#footer" className="transition-colors hover:text-foreground dark:hover:text-white">
              Privacy Policy
            </Link>
            <Link href="#footer" className="transition-colors hover:text-foreground dark:hover:text-white">
              Terms of Service
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}
