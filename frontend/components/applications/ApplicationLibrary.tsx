"use client";

import Link from "next/link";
import { useEffect, useState, type CSSProperties } from "react";

import ApplicationLogo, {
  isLogoDataUrl,
  normalizeLogoType,
} from "@/components/applications/ApplicationLogo";
import {
  appTheme,
  appThemeCssVars,
  getAppThemeDefinition,
} from "@/components/applications/appTheme";
import {
  getRegistryAnalysis,
  sourceProductLabels,
} from "@/lib/analysisRegistry";
import {
  deleteAnalyticalApplication,
  listAnalyticalApplications,
  normalizeApplicationSettings,
  type AnalyticalApplication,
} from "@/services/api";

function formatUpdated(value?: string) {
  if (!value) return "Updated recently";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "Updated recently";
  // Stable, locale-independent label avoids SSR/client hydration mismatch.
  const yyyy = date.getUTCFullYear();
  const mm = String(date.getUTCMonth() + 1).padStart(2, "0");
  const dd = String(date.getUTCDate()).padStart(2, "0");
  return `Updated ${yyyy}-${mm}-${dd}`;
}

function ApplicationTile({ app, onDelete }: {
  app: AnalyticalApplication;
  onDelete: (app: AnalyticalApplication) => void;
}) {
  const settings = normalizeApplicationSettings(app.settings);
  const definition = getAppThemeDefinition(settings.theme);
  const { tokens, chrome } = definition;
  const themeVars = appThemeCssVars(tokens, definition.id) as CSSProperties;

  const keys = (app.analyses || []).map((row) => row.analysis_key);
  const products = sourceProductLabels(keys);
  const names = keys
    .map((key) => getRegistryAnalysis(key)?.name || key)
    .slice(0, 5);
  const logoType = normalizeLogoType(settings.logo_type);
  const hasWordmark =
    logoType === "wordmark" &&
    Boolean(
      isLogoDataUrl(app.icon) ||
        (app.icon && app.icon.startsWith("http"))
    );

  const secondaryBtn: CSSProperties = {
    color: tokens.cyan,
    border: `1px solid ${tokens.borderActive}`,
    background: chrome.selectionBg,
    borderRadius: chrome.radiusButton,
    fontWeight: chrome.buttonWeight,
    minHeight: chrome.touchTarget,
    transitionDuration: chrome.durationFast,
  };
  const quietBtn: CSSProperties = {
    color: tokens.white,
    background: tokens.deepBlue,
    border: `1px solid ${tokens.border}`,
    borderRadius: chrome.radiusButton,
    minHeight: chrome.touchTarget,
    transitionDuration: chrome.durationFast,
  };

  return (
    <article
      data-app-theme={definition.id}
      data-app-scheme={definition.scheme}
      className="flex flex-col transition-all"
      style={{
        ...themeVars,
        background: tokens.midnight,
        color: tokens.white,
        border: `1px solid ${tokens.border}`,
        borderRadius: chrome.radiusCard,
        boxShadow: chrome.shadowCard,
        padding: chrome.cardPadding,
        fontFamily: chrome.fontSans,
        fontVariantNumeric: chrome.fontVariantNumeric,
        transitionDuration: chrome.durationNormal,
      }}
    >
      <div className="flex items-start gap-3">
        {hasWordmark ? (
          <div className="min-w-0 flex-1">
            <ApplicationLogo
              src={app.icon}
              name={app.name}
              variant="wordmark"
              size={40}
            />
            <p
              className="mt-2"
              style={{
                color: tokens.silver,
                fontSize: chrome.typeBody,
              }}
            >
              {app.description || names.join(" · ")}
            </p>
          </div>
        ) : (
          <>
            <ApplicationLogo
              src={app.icon}
              name={app.name}
              variant="square"
              size={36}
            />
            <div className="min-w-0 flex-1">
              <h2
                className="ip-heading font-semibold"
                style={{
                  color: tokens.white,
                  fontFamily: chrome.fontDisplay,
                  fontSize: chrome.typeSection,
                  letterSpacing: chrome.headingTracking,
                }}
              >
                {app.name}
              </h2>
              <p
                className="mt-2"
                style={{
                  color: tokens.silver,
                  fontSize: chrome.typeBody,
                }}
              >
                {app.description || names.join(" · ")}
              </p>
            </div>
          </>
        )}
      </div>

      <p
        className="mt-4 font-medium"
        style={{
          color: tokens.white,
          fontSize: chrome.typeBody,
        }}
      >
        {keys.length} analysis{keys.length === 1 ? "" : "es"}
      </p>
      {products ? (
        <p
          className="mt-1"
          style={{
            color: tokens.slate,
            fontSize: chrome.typeMeta,
            letterSpacing: chrome.labelTracking,
          }}
        >
          {products}
        </p>
      ) : null}
      <p
        className="mt-3"
        style={{
          color: tokens.slate,
          fontSize: chrome.typeMeta,
        }}
      >
        {formatUpdated(app.updated_at)}
        {app.is_published
          ? app.public_slug
            ? ` · Live /p/${app.public_slug}`
            : " · Live"
          : " · Draft"}
      </p>

      <div
        className="mt-6 flex flex-wrap gap-2"
        style={{ gap: chrome.space2 }}
      >
        <Link
          href={`/applications/${app.id}`}
          className="inline-flex items-center px-3 text-sm"
          style={{
            background: tokens.gradient,
            color: tokens.ctaText,
            borderRadius: chrome.radiusButton,
            fontWeight: chrome.buttonWeight,
            minHeight: chrome.touchTarget,
          }}
        >
          Open
        </Link>
        <Link
          href={
            app.is_published && app.public_slug
              ? `/p/${encodeURIComponent(app.public_slug)}`
              : `/applications/${app.id}/published`
          }
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center px-3 text-sm font-medium"
          style={secondaryBtn}
        >
          {app.is_published ? "Open live" : "Preview"}
        </Link>
        <Link
          href={`/applications/${app.id}/edit`}
          className="inline-flex items-center px-3 text-sm font-medium"
          style={quietBtn}
        >
          Edit
        </Link>
        <button
          type="button"
          onClick={() => onDelete(app)}
          className="inline-flex items-center px-3 text-sm font-medium transition-colors"
          style={{
            color: tokens.slate,
            borderRadius: chrome.radiusButton,
            minHeight: chrome.touchTarget,
            transitionDuration: chrome.durationFast,
          }}
        >
          Delete
        </button>
      </div>
    </article>
  );
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
          {apps.map((app) => (
            <ApplicationTile
              key={app.id}
              app={app}
              onDelete={(row) => void onDelete(row)}
            />
          ))}
        </div>
      ) : null}
    </div>
  );
}
