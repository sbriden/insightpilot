"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navigation = [
  {
    name: "Data Products",
    href: "/",
    isActive: (pathname: string) =>
      pathname === "/" ||
      pathname === "/create" ||
      pathname.startsWith("/products/"),
  },
  {
    name: "Analytical Applications",
    href: "/applications",
    isActive: (pathname: string) =>
      pathname === "/applications" ||
      pathname.startsWith("/applications/"),
  },
  {
    name: "Insights",
    href: "/insights",
    isActive: (pathname: string) => pathname === "/insights",
  },
  {
    name: "Opportunities",
    href: "/opportunities",
    isActive: (pathname: string) =>
      pathname === "/opportunities",
  },
  {
    name: "Data Refresh",
    href: "/refresh",
    isActive: (pathname: string) =>
      pathname === "/refresh" || pathname.startsWith("/refresh/"),
  },
  {
    name: "Data Quality",
    href: "/quality",
    isActive: (pathname: string) => pathname === "/quality",
  },
];

export default function AppNav() {
  // usePathname() can be null during early render / static shells.
  const pathname = usePathname() ?? "";

  return (
    <nav className="space-y-1 p-4">
      {navigation.map((item) => {
        const active = item.isActive(pathname);
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
  );
}
