"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { appTheme } from "@/components/applications/appTheme";
import ApplicationLogo from "@/components/applications/ApplicationLogo";
import {
  getRegistryAnalysis,
  sourceProductLabels,
} from "@/lib/analysisRegistry";
import {
  deleteAnalyticalApplication,
  listAnalyticalApplications,
  type AnalyticalApplication,
} from "@/services/api";

function formatUpdated(value?: string) {
  if (!value) return "Updated recently";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Updated recently";
  const deltaMs = Date.now() - date.getTime();
  const minutes = Math.round(deltaMs / 60000);
  if (minutes < 1) return "Updated just now";
  if (minutes < 60) return `Updated ${minutes} min ago`;
  const hours = Math.round(minutes / 60);
  if (hours < 24) return `Updated ${hours}h ago`;
  return `Updated ${date.toLocaleDateString()}`;
}

export default function ApplicationLibrary() {
  const [apps, setApps] = useState<AnalyticalApplication[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const rows = await listAnalyticalApplications();
      setApps(rows);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to load applications."
      );
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, []);

  async function onDelete(app: AnalyticalApplication) {
    const ok = window.confirm(
      `Delete “${app.name}”? This cannot be undone.`
    );
    if (!ok) return;
    await deleteAnalyticalApplication(app.id);
    await load();
  }

  return (
    <div className="mx-auto max-w-6xl space-y-8 px-6 py-8 lg:px-10 lg:py-10">
      <div className="flex items-center justify-between gap-4">
        <Link
          href="/"
          className="text-sm transition-colors"
          style={{ color: appTheme.slate }}
        >
          ← Portal
        </Link>
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: appTheme.cyan }}
        >
          InsightPilot
        </p>
      </div>

      <header className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1
            className="ip-heading text-3xl font-semibold tracking-tight lg:text-4xl"
            style={{ color: appTheme.white }}
          >
            Analytical Applications
          </h1>
          <p
            className="mt-2 max-w-2xl text-sm"
            style={{ color: appTheme.silver }}
          >
            Create focused analytical workspaces by combining analyses from
            your InsightPilot data products.
          </p>
        </div>
        <Link
          href="/applications/new"
          className="ip-app-cta rounded-lg px-4 py-2.5 text-sm"
        >
          + Create Application
        </Link>
      </header>

      {loading ? (
        <div
          className="ip-app-panel rounded-2xl px-8 py-12 text-center text-sm"
          style={{ color: appTheme.silver }}
        >
          <p
            className="text-[11px] font-semibold uppercase tracking-[0.2em]"
            style={{ color: appTheme.cyan }}
          >
            InsightPilot
          </p>
          <p className="mt-3">Initializing analytical workspace…</p>
        </div>
      ) : null}

      {error ? (
        <div
          className="rounded-2xl p-6 text-sm"
          style={{
            background: "rgba(255,85,112,0.08)",
            border: "1px solid rgba(255,85,112,0.35)",
            color: appTheme.negative,
          }}
        >
          {error}
        </div>
      ) : null}

      {!loading && !error && apps.length === 0 ? (
        <div className="ip-app-panel rounded-2xl px-8 py-16 text-center">
          <span
            className="inline-flex h-12 w-12 items-center justify-center rounded-full text-lg"
            style={{
              color: appTheme.cyan,
              border: `1px solid ${appTheme.borderActive}`,
              boxShadow: appTheme.glowSoft,
            }}
          >
            ◉
          </span>
          <h2
            className="ip-heading mt-5 text-2xl font-semibold"
            style={{ color: appTheme.white }}
          >
            Build an analytical workspace from the analyses you already use.
          </h2>
          <p
            className="mx-auto mt-3 max-w-xl text-sm"
            style={{ color: appTheme.silver }}
          >
            Select analyses from your existing InsightPilot data products and
            organize them into a single application.
          </p>
          <Link
            href="/applications/new"
            className="ip-app-cta mt-6 inline-flex rounded-lg px-4 py-2.5 text-sm"
          >
            + Create Your First Application
          </Link>
          <p
            className="mx-auto mt-6 max-w-lg text-xs"
            style={{ color: appTheme.slate }}
          >
            You can combine analyses from multiple data products. Your
            application does not create new data—it creates a new way to work
            with the analyses you already have.
          </p>
        </div>
      ) : null}

      {!loading && apps.length > 0 ? (
        <div className="grid gap-4 lg:grid-cols-2">
          {apps.map((app) => {
            const keys = (app.analyses || []).map((row) => row.analysis_key);
            const products = sourceProductLabels(keys);
            const names = keys
              .map((key) => getRegistryAnalysis(key)?.name || key)
              .slice(0, 5);
            return (
              <article
                key={app.id}
                className="ip-app-panel flex flex-col rounded-2xl p-6 transition-all duration-200"
              >
                <div className="flex items-start gap-3">
                  <ApplicationLogo
                    src={app.icon}
                    name={app.name}
                    size={36}
                  />
                  <div className="min-w-0 flex-1">
                    <h2
                      className="ip-heading text-xl font-semibold"
                      style={{ color: appTheme.white }}
                    >
                      {app.name}
                    </h2>
                    <p
                      className="mt-2 text-sm"
                      style={{ color: appTheme.silver }}
                    >
                      {app.description || names.join(" · ")}
                    </p>
                  </div>
                </div>
                <p
                  className="mt-4 text-sm font-medium"
                  style={{ color: appTheme.white }}
                >
                  {keys.length} analysis{keys.length === 1 ? "" : "es"}
                </p>
                {products ? (
                  <p className="mt-1 text-xs" style={{ color: appTheme.slate }}>
                    {products}
                  </p>
                ) : null}
                <p className="mt-3 text-xs" style={{ color: appTheme.slate }}>
                  {formatUpdated(app.updated_at)}
                </p>
                <div className="mt-6 flex flex-wrap gap-2">
                  <Link
                    href={`/applications/${app.id}`}
                    className="ip-app-cta rounded-lg px-3 py-1.5 text-sm"
                  >
                    Open
                  </Link>
                  <Link
                    href={`/applications/${app.id}/edit`}
                    className="rounded-lg px-3 py-1.5 text-sm font-medium"
                    style={{
                      color: appTheme.white,
                      background: appTheme.deepBlue,
                      border: `1px solid ${appTheme.border}`,
                    }}
                  >
                    Edit
                  </Link>
                  <button
                    type="button"
                    onClick={() => void onDelete(app)}
                    className="rounded-lg px-3 py-1.5 text-sm font-medium transition-colors"
                    style={{ color: appTheme.slate }}
                  >
                    Delete
                  </button>
                </div>
              </article>
            );
          })}
        </div>
      ) : null}
    </div>
  );
}
