import type { Metadata } from "next";
import Link from "next/link";
import { isAuthConfigured } from "@/lib/auth";
import "./globals.css";

export const metadata: Metadata = {
  title: "Staccato Ops",
  description: "Internal ops tooling for the Staccato video pacing scorer",
};

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/jobs", label: "Jobs" },
  { href: "/classify", label: "Classify" },
  { href: "/moderation", label: "Moderation" },
  { href: "/engine", label: "Engine" },
];

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const authDisabled = !isAuthConfigured();
  return (
    <html lang="en">
      <body>
        <header className="topbar">
          <div className="brand">
            Staccato <span>/ ops</span>
          </div>
          <nav>
            {NAV.map((item) => (
              <Link key={item.href} href={item.href}>
                {item.label}
              </Link>
            ))}
          </nav>
        </header>
        {authDisabled && (
          <div className="dev-banner">
            auth disabled — dev mode. Set CLERK_SECRET_KEY and
            NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY (and wire in Clerk middleware,
            see README) before deploying.
          </div>
        )}
        <main>{children}</main>
      </body>
    </html>
  );
}
