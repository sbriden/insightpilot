import { NextRequest, NextResponse } from "next/server";

const ADMIN_COOKIE = "ip_admin";

function apiBaseUrl(): string {
  // Prefer runtime API_URL so login works even if NEXT_PUBLIC_* was
  // wrong/missing at image build time.
  const raw = (
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  ).trim();
  return raw.replace(/\/$/, "").replace(/\/api$/i, "");
}

function detailFromPayload(payload: unknown, status: number): string {
  if (payload && typeof payload === "object" && "detail" in payload) {
    const detail = (payload as { detail?: unknown }).detail;
    if (typeof detail === "string" && detail.trim()) {
      return detail;
    }
  }
  if (status === 404) {
    return (
      "API login endpoint not found. On insightpilot-web, set API_URL " +
      "and NEXT_PUBLIC_API_URL to your API service URL " +
      "(e.g. https://insightpilot-api.onrender.com), then rebuild/redeploy."
    );
  }
  if (status === 401) {
    return "Invalid password.";
  }
  return `Login failed (HTTP ${status}).`;
}

export async function POST(request: NextRequest) {
  const body = await request.json().catch(() => ({}));
  const password = String(body?.password || "");
  const base = apiBaseUrl();
  const loginUrl = `${base}/api/admin/login`;

  let upstream: Response;
  try {
    upstream = await fetch(loginUrl, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ password }),
      cache: "no-store",
    });
  } catch {
    return NextResponse.json(
      {
        detail:
          `Unable to reach API at ${base}. Set API_URL / NEXT_PUBLIC_API_URL ` +
          "to your insightpilot-api URL and redeploy the web service.",
      },
      { status: 502 }
    );
  }

  const payload = await upstream.json().catch(() => ({}));
  if (!upstream.ok) {
    return NextResponse.json(
      { detail: detailFromPayload(payload, upstream.status) },
      { status: upstream.status }
    );
  }

  const response = NextResponse.json(payload);
  const token = String(
    payload && typeof payload === "object" && "token" in payload
      ? (payload as { token?: unknown }).token || ""
      : ""
  );
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
