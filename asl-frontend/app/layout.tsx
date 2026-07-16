import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: {
    default: "ASL — see how fast anything cuts",
    template: "%s — ASL",
  },
  description:
    "ASL measures how fast a video changes shots: a 0-100 pacing intensity score and a timeline heat map of cut density.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>
        <header className="siteHeader">
          <div className="container">
            <Link href="/" className="wordmark">
              ASL<span>.</span>
            </Link>
            <nav className="siteNav">
              <Link href="/leaderboard">Leaderboard</Link>
              <Link href="/methodology">Methodology</Link>
              <a href="https://apps.apple.com" rel="noopener">
                Get the iOS app
              </a>
            </nav>
          </div>
        </header>
        <main className="container">{children}</main>
        <footer className="siteFooter">
          <div className="container">
            <span>ASL — a pacing instrument for video.</span>
            <span>
              Scores are versioned and never silently rescored.{" "}
              <Link href="/methodology">How it works</Link>
            </span>
          </div>
        </footer>
      </body>
    </html>
  );
}
