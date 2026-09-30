"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import AppNav from "@/components/layout/AppNav";

interface AppShellProps {
  children: React.ReactNode;
}

/**
 * Portal chrome for discovery. All Analytical Applications routes
 * use the immersive command-center shell (no portal nav).
 */
export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname() ?? "";
  const isApplications = pathname.startsWith("/applications");

  if (isApplications) {
    return <div className="ip-app min-h-screen">{children}</div>;
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="flex min-h-screen">
        <aside className="hidden w-64 border-r bg-white lg:block">
          <div className="flex h-16 items-center border-b px-6">
            <Link href="/" className="text-xl font-bold">
              InsightPilot
            </Link>
          </div>
          <AppNav />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="flex h-16 items-center justify-between border-b bg-white px-6">
            <div>
              <h1 className="text-lg font-semibold">InsightPilot</h1>
            </div>
            <div className="flex items-center gap-4">
              <Link
                href="/applications/new"
                className="rounded-lg border border-gray-300 bg-white px-3 py-1.5 text-sm font-medium text-gray-800 hover:bg-gray-50"
              >
                Create application
              </Link>
              <Link
                href="/create"
                className="rounded-lg bg-gray-900 px-3 py-1.5 text-sm font-medium text-white hover:bg-gray-800"
              >
                Create data product
              </Link>
              <div className="text-sm text-gray-500">
                Data Intelligence Platform
              </div>
            </div>
          </header>

          <main className="flex-1 p-6 lg:p-8">{children}</main>
        </div>
      </div>
    </div>
  );
}
