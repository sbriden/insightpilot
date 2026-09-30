"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

import CreateApplicationWizard from "@/components/applications/CreateApplicationWizard";
import { appTheme } from "@/components/applications/appTheme";
import {
  getAnalyticalApplication,
  type AnalyticalApplication,
} from "@/services/api";

export default function EditApplicationPage() {
  const params = useParams();
  const id = String(params?.id || "");
  const [app, setApp] = useState<AnalyticalApplication | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    (async () => {
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
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [id]);

  if (error) {
    return (
      <div className="p-8 text-sm" style={{ color: appTheme.negative }}>
        {error}{" "}
        <Link href="/applications" className="underline" style={{ color: appTheme.cyan }}>
          Back
        </Link>
      </div>
    );
  }

  if (!app) {
    return (
      <div
        className="flex min-h-screen items-center justify-center text-sm"
        style={{ color: appTheme.silver }}
      >
        Loading…
      </div>
    );
  }

  return <CreateApplicationWizard mode="edit" existing={app} />;
}
