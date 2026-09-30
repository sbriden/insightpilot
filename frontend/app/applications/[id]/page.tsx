"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import ApplicationWorkspace from "@/components/applications/ApplicationWorkspace";
import { appTheme } from "@/components/applications/appTheme";
import {
  getAnalyticalApplication,
  type AnalyticalApplication,
} from "@/services/api";

export default function ApplicationPage() {
  const params = useParams();
  const id = String(params?.id || "");
  const [app, setApp] = useState<AnalyticalApplication | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      setLoading(true);
      try {
        const row = await getAnalyticalApplication(id);
        if (!cancelled) setApp(row);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load application."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3">
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: appTheme.cyan }}
        >
          InsightPilot
        </p>
        <p className="text-sm" style={{ color: appTheme.silver }}>
          Initializing analytical workspace…
        </p>
        <div
          className="mt-2 h-0.5 w-40 overflow-hidden rounded-full"
          style={{ background: appTheme.deepBlue }}
        >
          <div
            className="h-full w-1/2 animate-pulse rounded-full"
            style={{
              background: appTheme.gradient,
              boxShadow: appTheme.glowSoft,
            }}
          />
        </div>
      </div>
    );
  }

  if (error || !app) {
    return (
      <div className="mx-auto flex min-h-screen max-w-lg flex-col justify-center gap-4 p-8">
        <h1
          className="ip-heading text-xl font-semibold"
          style={{ color: appTheme.white }}
        >
          Application unavailable
        </h1>
        <p className="text-sm" style={{ color: appTheme.silver }}>
          {error || "Not found."}
        </p>
        <Link
          href="/applications"
          className="text-sm font-medium underline"
          style={{ color: appTheme.cyan }}
        >
          ← Return to Analytical Applications
        </Link>
      </div>
    );
  }

  return <ApplicationWorkspace application={app} />;
}
