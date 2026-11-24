import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import { Pointer } from "@/components/ui/pointer";
import "./globals.css";
import { Providers } from "./providers";

const manrope = Manrope({
  variable: "--font-manrope",
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
  display: "swap",
});

export const metadata: Metadata = {
  title: "NEXUS — AI-Powered B2B Lead Generation",
  description:
    "Discover relevant B2B prospects, research businesses, qualify opportunities, and automate personalized outreach in one intelligent platform.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en" suppressHydrationWarning className={`${manrope.variable} h-full`}>
      <body className="min-h-full flex flex-col">
        <Pointer className="fill-primary stroke-white text-primary dark:fill-lime-400 dark:stroke-[#0A140C] dark:text-lime-400" />
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
