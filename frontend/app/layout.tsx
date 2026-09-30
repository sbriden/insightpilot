import type { Metadata } from "next";
import AppShell from "@/components/layout/AppShell";
import { Geist, Geist_Mono, Inter, Space_Grotesk } from "next/font/google";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const appSans = Inter({
  variable: "--font-app-sans",
  subsets: ["latin"],
});

const appDisplay = Space_Grotesk({
  variable: "--font-app-display",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "InsightPilot",
  description: "Data intelligence platform",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} ${appSans.variable} ${appDisplay.variable} h-full antialiased`}
    >
      <body className="min-h-full flex flex-col">
        <AppShell>{children}</AppShell>
      </body>
    </html>
  );
}
