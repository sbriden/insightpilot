import { NextRequest, NextResponse } from "next/server";

const ADMIN_COOKIE = "ip_admin";
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const password = String(body?.password || "");

  const upstream = await fetch(`${API_BASE_URL}/api/admin/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
    cache: "no-store",
  });

  const payload = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return NextResponse.json(
      { detail: payload?.detail || "Invalid password." },
      { status: upstream.status }
    );
  }

  const response = NextResponse.json(payload);
  const token = String(payload?.token || "");
  if (token) {
    const secure =
      process.env.NODE_ENV === "production" ||
      request.nextUrl.protocol === "https:";
    response.cookies.set({
      name: ADMIN_COOKIE,
      value: token,
      httpOnly: true,
      sameSite: "lax",
      secure,
      path: "/",
      maxAge: 60 * 60 * 24 * 30,
    });
  }
  return response;
}

export async function DELETE() {
  const response = NextResponse.json({ ok: true });
  response.cookies.set({
    name: ADMIN_COOKIE,
    value: "",
    httpOnly: true,
    sameSite: "lax",
    path: "/",
    maxAge: 0,
  });
  return response;
}
