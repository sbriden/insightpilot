"use client";

import { useMemo, useState } from "react";

import { appTheme } from "@/components/applications/appTheme";
import {
  updateAnalyticalApplication,
  type AnalyticalApplication,
} from "@/services/api";

type Props = {
  application: AnalyticalApplication;
  onUpdated?: (app: AnalyticalApplication) => void;
};

function publicPathUrl(slug: string | null | undefined): string | null {
  if (!slug || typeof window === "undefined") return null;
  return `${window.location.origin}/p/${encodeURIComponent(slug)}`;
}

export default function PublishApplicationPanel({
  application,
  onUpdated,
}: Props) {
  const [slug, setSlug] = useState(application.public_slug || "");
  const [domain, setDomain] = useState(application.custom_domain || "");
  const [published, setPublished] = useState(
    Boolean(application.is_published)
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  const pathUrl = useMemo(() => publicPathUrl(slug.trim() || null), [slug]);

  async function save(nextPublished = published) {
    setSaving(true);
    setError(null);
    setMessage(null);
    try {
      if (nextPublished && !slug.trim()) {
        throw new Error("Set a public slug before publishing.");
      }
      const updated = await updateAnalyticalApplication(application.id, {
        is_published: nextPublished,
        public_slug: slug.trim() || null,
        custom_domain: domain.trim() || null,
      });
      setPublished(Boolean(updated.is_published));
      setSlug(updated.public_slug || "");
      setDomain(updated.custom_domain || "");
      setMessage(
        updated.is_published
          ? "Published. Public visitors can open the path URL (and custom domain once DNS is set)."
          : "Unpublished. Public URLs will return not found."
      );
      onUpdated?.(updated);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Unable to update publish settings."
      );
    } finally {
      setSaving(false);
    }
  }

  async function copy(text: string) {
    try {
      await navigator.clipboard.writeText(text);
      setMessage("Copied to clipboard.");
    } catch {
      setMessage(text);
    }
  }

  return (
    <section
      className="space-y-4 rounded-2xl p-4"
      style={{
        background: appTheme.midnight,
        border: `1px solid ${appTheme.border}`,
      }}
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2
            className="ip-heading text-lg font-semibold"
            style={{ color: appTheme.white }}
          >
            Publish
          </h2>
          <p className="mt-1 text-sm" style={{ color: appTheme.silver }}>
            Path URL on this host, plus an optional custom domain (CNAME to
            your Render web service).
          </p>
        </div>
        <span
          className="rounded-full px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wide"
          style={{
            color: published ? appTheme.cyan : appTheme.slate,
            border: `1px solid ${published ? appTheme.borderActive : appTheme.border}`,
            background: published
              ? "rgba(0,229,255,0.08)"
              : "transparent",
          }}
        >
          {published ? "Live" : "Draft"}
        </span>
      </div>

      <label className="block space-y-1.5">
        <span className="text-xs font-medium" style={{ color: appTheme.slate }}>
          Public slug
        </span>
        <div className="flex gap-2">
          <span
            className="inline-flex items-center rounded-lg px-2 text-sm"
            style={{ color: appTheme.slate }}
          >
            /p/
          </span>
          <input
            value={slug}
            onChange={(event) => setSlug(event.target.value)}
            placeholder="betting-slate"
            className="min-w-0 flex-1 rounded-lg px-3 py-2 text-sm outline-none"
            style={{
              background: appTheme.deepBlue,
              color: appTheme.white,
              border: `1px solid ${appTheme.border}`,
            }}
          />
        </div>
      </label>

      <label className="block space-y-1.5">
        <span className="text-xs font-medium" style={{ color: appTheme.slate }}>
          Custom domain (optional)
        </span>
        <input
          value={domain}
          onChange={(event) => setDomain(event.target.value)}
          placeholder="betting.example.com"
          className="w-full rounded-lg px-3 py-2 text-sm outline-none"
          style={{
            background: appTheme.deepBlue,
            color: appTheme.white,
            border: `1px solid ${appTheme.border}`,
          }}
        />
        <p className="text-xs" style={{ color: appTheme.slate }}>
          Add the domain on your Render web service, then CNAME it to the
          Render hostname.
        </p>
      </label>

      {pathUrl ? (
        <div className="flex flex-wrap items-center gap-2">
          <code
            className="max-w-full truncate rounded px-2 py-1 text-xs"
            style={{
              color: appTheme.cyan,
              background: "rgba(0,229,255,0.08)",
            }}
          >
            {pathUrl}
          </code>
          <button
            type="button"
            onClick={() => void copy(pathUrl)}
            className="text-xs font-medium"
            style={{ color: appTheme.silver }}
          >
            Copy
          </button>
        </div>
      ) : null}

      {domain.trim() ? (
        <div className="flex flex-wrap items-center gap-2">
          <code
            className="max-w-full truncate rounded px-2 py-1 text-xs"
            style={{
              color: appTheme.cyan,
              background: "rgba(0,229,255,0.08)",
            }}
          >
            https://{domain.trim().toLowerCase()}
          </code>
          <button
            type="button"
            onClick={() =>
              void copy(`https://${domain.trim().toLowerCase()}`)
            }
            className="text-xs font-medium"
            style={{ color: appTheme.silver }}
          >
            Copy
          </button>
        </div>
      ) : null}

      {error ? (
        <p className="text-sm" style={{ color: "#f87171" }}>
          {error}
        </p>
      ) : null}
      {message ? (
        <p className="text-sm" style={{ color: appTheme.silver }}>
          {message}
        </p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <button
          type="button"
          disabled={saving}
          onClick={() => void save(true)}
          className="ip-app-cta rounded-lg px-3 py-1.5 text-sm disabled:opacity-60"
        >
          {published ? "Update & keep live" : "Publish"}
        </button>
        {published ? (
          <button
            type="button"
            disabled={saving}
            onClick={() => void save(false)}
            className="rounded-lg px-3 py-1.5 text-sm font-medium disabled:opacity-60"
            style={{
              color: appTheme.white,
              border: `1px solid ${appTheme.border}`,
            }}
          >
            Unpublish
          </button>
        ) : (
          <button
            type="button"
            disabled={saving}
            onClick={() => void save(false)}
            className="rounded-lg px-3 py-1.5 text-sm font-medium disabled:opacity-60"
            style={{
              color: appTheme.silver,
              border: `1px solid ${appTheme.border}`,
            }}
          >
            Save draft settings
          </button>
        )}
      </div>
    </section>
  );
}
