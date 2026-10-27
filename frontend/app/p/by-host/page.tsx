"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import ApplicationWorkspace from "@/components/applications/ApplicationWorkspace";
import { appTheme } from "@/components/applications/appTheme";
import {
  getPublishedApplicationByDomain,
  type AnalyticalApplication,
} from "@/services/api";

function ByHostLoader() {
  const searchParams = useSearchParams();
  const [app, setApp] = useState<AnalyticalApplication | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const host =
        searchParams.get("host") ||
        (typeof window !== "undefined" ? window.location.host : "");
      if (!host) {
        setError("Missing host.");
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const row = await getPublishedApplicationByDomain(host);
        if (!cancelled) setApp(row);
      } catch (err) {
        if (!cancelled) {
          setError(
            err instanceof Error
              ? err.message
              : "Unable to load published application."
          );
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [searchParams]);

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3">
        <p className="text-sm" style={{ color: appTheme.silver }}>
          Loading…
        </p>
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
          {error || "No published application is mapped to this domain."}
        </p>
      </div>
    );
  }

  return <ApplicationWorkspace application={app} mode="published" />;
}

export default function PublicHostApplicationPage() {
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
      <ByHostLoader />
    </Suspense>
  );
}
