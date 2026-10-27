"use client";

import { FormEvent, Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";

import { appTheme } from "@/components/applications/appTheme";
import {
  getAdminAuthStatus,
  setAdminToken,
} from "@/services/api";

function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const nextPath = searchParams.get("next") || "/applications";
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const status = await getAdminAuthStatus();
        if (!cancelled && !status.auth_required) {
          router.replace(nextPath);
        }
      } catch {
        // Stay on login if status check fails.
      } finally {
        if (!cancelled) setChecking(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [nextPath, router]);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const session = await fetch("/api/admin/session", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password }),
      });
      const payload = await session.json().catch(() => ({}));
      if (!session.ok) {
        throw new Error(
          typeof payload?.detail === "string"
            ? payload.detail
            : "Invalid password."
        );
      }
      if (payload?.token) {
        setAdminToken(String(payload.token));
      }
      router.replace(nextPath);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to sign in."
      );
    } finally {
      setLoading(false);
    }
  }

  if (checking) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <p className="text-sm" style={{ color: appTheme.silver }}>
          Checking access…
        </p>
      </div>
    );
  }

  return (
    <div
      className="flex min-h-screen items-center justify-center px-6"
      style={{ background: appTheme.obsidian }}
    >
      <form
        onSubmit={(event) => void onSubmit(event)}
        className="w-full max-w-sm space-y-5 rounded-2xl p-6"
        style={{
          background: appTheme.midnight,
          border: `1px solid ${appTheme.border}`,
        }}
      >
        <div>
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.2em]"
            style={{ color: appTheme.cyan }}
          >
            InsightPilot
          </p>
          <h1
            className="ip-heading mt-2 text-2xl font-semibold"
            style={{ color: appTheme.white }}
          >
            Admin sign in
          </h1>
          <p className="mt-2 text-sm" style={{ color: appTheme.silver }}>
            Personal / admin access for the studio. Published apps stay public.
          </p>
        </div>
        <label className="block space-y-2">
          <span className="text-sm" style={{ color: appTheme.silver }}>
            Password
          </span>
          <input
            type="password"
            autoComplete="current-password"
            value={password}
            onChange={(event) => setPassword(event.target.value)}
            className="w-full rounded-lg px-3 py-2 text-sm outline-none"
            style={{
              background: appTheme.deepBlue,
              color: appTheme.white,
              border: `1px solid ${appTheme.border}`,
            }}
          />
        </label>
        {error ? (
          <p className="text-sm" style={{ color: appTheme.negative }}>
            {error}
          </p>
        ) : null}
        <button
          type="submit"
          disabled={loading || !password}
          className="ip-app-cta w-full rounded-lg px-3 py-2 text-sm disabled:opacity-60"
        >
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}

export default function LoginPage() {
  return (
    <Suspense
      fallback={
        <div className="flex min-h-screen items-center justify-center">
          <p className="text-sm" style={{ color: appTheme.silver }}>
            Loading…
          </p>
        </div>
      }
    >
      <LoginForm />
    </Suspense>
  );
}
