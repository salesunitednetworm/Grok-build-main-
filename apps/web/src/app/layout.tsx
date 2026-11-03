import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Fieldline Energy",
  description:
    "Contractor home-energy workspace. OpenStudio-HPXML / EnergyPlus. Not DOE HOMES approved.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar">
            <Link className="brand" href="/">
              Fieldline
              <span>OpenStudio-HPXML 1.12.0 · EnergyPlus 25.2.0</span>
            </Link>
            <nav className="nav">
              <Link href="/">Homes</Link>
              <Link href="/projects">Job board</Link>
              <span>Not a DOE HOMES or ACCA-listed product</span>
            </nav>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
