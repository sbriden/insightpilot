import { NextRequest, NextResponse } from "next/server";

const ADMIN_COOKIE = "ip_admin";

function primaryHosts(): Set<string> {
  const raw =
    process.env.NEXT_PUBLIC_PRIMARY_HOSTS ||
    "localhost:3000,127.0.0.1:3000";
  return new Set(
    raw
      .split(",")
      .map((part) => part.trim().toLowerCase())
      .filter(Boolean)
  );
}

function isPublicPath(pathname: string): boolean {
  if (
    pathname.startsWith("/p/") ||
    pathname === "/p" ||
    pathname === "/login" ||
    pathname.startsWith("/api/admin/")
  ) {
    return true;
  }
  if (
    pathname.startsWith("/_next/") ||
    pathname.startsWith("/favicon") ||
    pathname.endsWith(".ico") ||
    pathname.endsWith(".svg") ||
    pathname.endsWith(".png") ||
    pathname.endsWith(".jpg") ||
    pathname.endsWith(".webp")
  ) {
    return true;
  }
  return false;
}

function authRequired(): boolean {
  // NEXT_PUBLIC_* is available to Edge middleware after Docker build.
  // ADMIN_PASSWORD alone may be runtime-only and missing on Edge.
  const flag = (process.env.NEXT_PUBLIC_REQUIRE_ADMIN_AUTH || "").trim();
  if (flag === "1" || flag.toLowerCase() === "true") {
    return true;
  }
  return Boolean((process.env.ADMIN_PASSWORD || "").trim());
}

export function middleware(request: NextRequest) {
  const host = (request.headers.get("host") || "")
    .toLowerCase()
    .split(",")[0]
    .trim();
  const { pathname } = request.nextUrl;
  const primaries = primaryHosts();
  const isPrimaryHost = !host || primaries.has(host);

  // Custom domain → public published shell resolved by Host.
  if (!isPrimaryHost && !pathname.startsWith("/_next/")) {
    if (
      pathname.startsWith("/p/") ||
      pathname === "/login" ||
      pathname.startsWith("/api/")
    ) {
      return NextResponse.next();
    }
    const rewriteUrl = request.nextUrl.clone();
    rewriteUrl.pathname = "/p/by-host";
    rewriteUrl.searchParams.set("host", host);
    return NextResponse.rewrite(rewriteUrl);
  }

  if (!authRequired() || isPublicPath(pathname)) {
    return NextResponse.next();
  }

  const token = request.cookies.get(ADMIN_COOKIE)?.value;
  if (!token) {
    const loginUrl = request.nextUrl.clone();
    loginUrl.pathname = "/login";
    loginUrl.searchParams.set(
      "next",
      `${pathname}${request.nextUrl.search || ""}`
    );
    return NextResponse.redirect(loginUrl);
  }

  return NextResponse.next();
}

export const config = {
  matcher: ["/((?!_next/static|_next/image).*)"],
};
