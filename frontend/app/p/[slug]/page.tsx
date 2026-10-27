"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import ApplicationWorkspace from "@/components/applications/ApplicationWorkspace";
import { appTheme } from "@/components/applications/appTheme";
import {
  getPublishedApplicationBySlug,
  type AnalyticalApplication,
} from "@/services/api";

export default function PublicSlugApplicationPage() {
  const params = useParams();
  const slug = String(params?.slug || "");
  const [app, setApp] = useState<AnalyticalApplication | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    (async () => {
      if (!slug) {
        setError("Missing application slug.");
        setLoading(false);
        return;
      }
      setLoading(true);
      try {
        const row = await getPublishedApplicationBySlug(slug);
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
  }, [slug]);

  if (loading) {
    return (
      <div className="flex min-h-screen flex-col items-center justify-center gap-3">
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: appTheme.cyan }}
        >
          Loading
        </p>
        <p className="text-sm" style={{ color: appTheme.silver }}>
          Opening published application…
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
          {error || "This published application was not found."}
        </p>
      </div>
    );
  }

  return <ApplicationWorkspace application={app} mode="published" />;
}
