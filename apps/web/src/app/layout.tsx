import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Home Energy Modeling Platform",
  description:
    "Canonical building models, HPXML, and OpenStudio-HPXML / EnergyPlus. Not DOE HOMES approved.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body>
        <div className="shell">
          <header className="topbar">
            <Link className="brand" href="/">
              Home Energy Modeling
              <span>OpenStudio-HPXML 1.12.0 · EnergyPlus 25.2.0</span>
            </Link>
            <p className="fine">Not a DOE HOMES or ACCA-listed product</p>
          </header>
          {children}
        </div>
      </body>
    </html>
  );
}
