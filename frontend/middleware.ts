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

function isPrimaryHostName(host: string): boolean {
  if (!host) return true;
  const normalized = host.toLowerCase();
  const primaries = primaryHosts();
  if (primaries.has(normalized)) return true;
  // Host header may omit or include :443; also allow bare hostname match.
  const bare = normalized.split(":")[0];
  if (primaries.has(bare)) return true;
  for (const primary of primaries) {
    if (primary.split(":")[0] === bare) return true;
  }
  // Default Render service hostnames are the admin/studio app, not
  // customer custom domains. Without this, a missing PRIMARY_HOSTS
  // env rewrites every page to /p/by-host → "Not found".
  if (bare.endsWith(".onrender.com")) return true;
  return false;
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
  const isPrimaryHost = isPrimaryHostName(host);

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
