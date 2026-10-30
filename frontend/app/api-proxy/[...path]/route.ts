import { NextRequest, NextResponse } from "next/server";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

function apiBaseUrl(): string {
  const raw = (
    process.env.API_URL ||
    process.env.NEXT_PUBLIC_API_URL ||
    "http://localhost:8000"
  ).trim();
  return raw.replace(/\/$/, "").replace(/\/api$/i, "");
}

function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

async function fetchUpstream(
  target: string,
  init: RequestInit,
  attempts = 2
): Promise<Response> {
  let lastError: unknown;
  for (let attempt = 1; attempt <= attempts; attempt++) {
    try {
      const response = await fetch(target, {
        ...init,
        cache: "no-store",
        redirect: "manual",
      });
      // Free-tier APIs often return Render HTML 502 while waking up.
      if (
        (response.status === 502 || response.status === 503) &&
        attempt < attempts
      ) {
        await sleep(2500 * attempt);
        continue;
      }
      return response;
    } catch (error) {
      lastError = error;
      if (attempt >= attempts) break;
      await sleep(2500 * attempt);
    }
  }
  throw lastError instanceof Error
    ? lastError
    : new Error("Upstream request failed.");
}

async function toProxyResponse(
  upstream: Response,
  target: string
): Promise<NextResponse> {
  const contentType = upstream.headers.get("content-type") || "";
  const isHtml =
    contentType.includes("text/html") ||
    upstream.status === 502 ||
    upstream.status === 503;

  if (isHtml) {
    const body = await upstream.text();
    const looksLikeRenderGateway =
      body.includes("Bad Gateway") ||
      body.includes("This service is currently unavailable") ||
      body.includes("502");
    return NextResponse.json(
      {
        detail: looksLikeRenderGateway
          ? `API unavailable (${upstream.status}) at ${apiBaseUrl()}. ` +
            "On Render free tier the API sleeps after idle time or may still " +
            "be waking/crashing. Open the API health URL directly and wait " +
            "until it returns JSON, then reload the app. Green Deployed ≠ running."
          : `Upstream returned non-JSON (${upstream.status}) for ${target}.`,
        status: upstream.status,
        target,
      },
      { status: 502 }
    );
  }

  const responseHeaders = new Headers();
  if (contentType) responseHeaders.set("content-type", contentType);
  return new NextResponse(upstream.body, {
    status: upstream.status,
    headers: responseHeaders,
  });
}

async function proxy(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  const { path } = await context.params;
  const suffix = (path || []).join("/");
  const incoming = new URL(request.url);
  const target = `${apiBaseUrl()}/${suffix}${incoming.search}`;

  const headers = new Headers();
  const passThrough = [
    "content-type",
    "authorization",
    "x-admin-token",
    "accept",
  ];
  for (const key of passThrough) {
    const value = request.headers.get(key);
    if (value) headers.set(key, value);
  }

  let body: ArrayBuffer | undefined;
  if (request.method !== "GET" && request.method !== "HEAD") {
    body = await request.arrayBuffer();
  }

  try {
    const upstream = await fetchUpstream(target, {
      method: request.method,
      headers,
      body,
    });
    return toProxyResponse(upstream, target);
  } catch (error) {
    return NextResponse.json(
      {
        detail:
          `Unable to reach API at ${apiBaseUrl()}. ` +
          "Confirm API_URL on the web service, then open " +
          `${apiBaseUrl()}/api/health in a browser and wait for JSON ` +
          "(cold starts on free Render can take 30–60s).",
        cause: error instanceof Error ? error.message : String(error),
      },
      { status: 502 }
    );
  }
}

export async function GET(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}

export async function POST(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}

export async function PUT(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}

export async function PATCH(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}

export async function DELETE(
  request: NextRequest,
  context: { params: Promise<{ path: string[] }> }
) {
  return proxy(request, context);
}
