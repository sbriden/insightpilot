"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

interface AppShellProps {
  children: React.ReactNode;
}

const navigation = [
  {
    name: "Data Products",
    href: "/",
    isActive: (
      pathname: string
    ) =>
      pathname === "/" ||
      pathname === "/create" ||
      pathname.startsWith("/products/"),
  },
  {
    name: "Insights",
    href: "/insights",
    isActive: (
      pathname: string
    ) =>
      pathname === "/insights",
  },
  {
    name: "Opportunities",
    href: "/opportunities",
    isActive: (
      pathname: string
    ) =>
      pathname === "/opportunities",
  },
  {
    name: "Data Quality",
    href: "/quality",
    isActive: (
      pathname: string
    ) =>
      pathname === "/quality",
  },
];

export default function AppShell({
  children,
}: AppShellProps) {
  const pathname = usePathname();

  return (
    <div className="min-h-screen bg-gray-50">

      <div className="flex min-h-screen">

        {/* Sidebar */}

        <aside className="hidden w-64 border-r bg-white lg:block">

          <div className="flex h-16 items-center border-b px-6">

            <Link
              href="/"
              className="text-xl font-bold"
            >
              InsightPilot
            </Link>

          </div>

          <nav className="space-y-1 p-4">

            {navigation.map((item) => {

              const active =
                item.isActive(pathname);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  className={[
                    "block rounded-lg px-4 py-3 text-sm font-medium transition",
                    active
                      ? "bg-gray-100 text-gray-900"
                      : "text-gray-600 hover:bg-gray-50 hover:text-gray-900",
                  ].join(" ")}
                >
                  {item.name}
                </Link>
              );
            })}

          </nav>

        </aside>

        {/* Main */}

        <div className="flex min-w-0 flex-1 flex-col">

          {/* Header */}

          <header className="flex h-16 items-center justify-between border-b bg-white px-6">

            <div>
              <h1 className="text-lg font-semibold">
                InsightPilot
              </h1>
            </div>

            <div className="flex items-center gap-4">

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

          {/* Content */}

          <main className="flex-1 p-6 lg:p-8">
            {children}
          </main>

        </div>

      </div>

    </div>

  );
}
