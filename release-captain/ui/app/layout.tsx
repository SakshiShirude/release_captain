import type { ReactNode } from "react";
import type { Metadata } from "next";
import { Manrope } from "next/font/google";
import { AppShell } from "../components/AppShell";
import "./globals.css";

const manrope = Manrope({
  subsets: ["latin"],
  variable: "--font-sans",
  display: "swap",
});

export const metadata: Metadata = {
  title: "Release Captain",
  description: "Review release evidence, test results, proposed actions and approvals.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en" suppressHydrationWarning>
      <body className={manrope.variable}>
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
