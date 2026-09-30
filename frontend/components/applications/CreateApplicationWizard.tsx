"use client";

import Link from "next/link";
import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";

import { appTheme } from "@/components/applications/appTheme";
import ApplicationLogo, {
  fileToLogoDataUrl,
} from "@/components/applications/ApplicationLogo";
import {
  ANALYSIS_REGISTRY,
  getRegistryAnalysis,
  groupRegistryByProduct,
} from "@/lib/analysisRegistry";
import {
  createAnalyticalApplication,
  updateAnalyticalApplication,
  type AnalyticalApplication,
  type AnalyticalApplicationAnalysis,
} from "@/services/api";

type Step = "name" | "select" | "organize";

interface Props {
  mode?: "create" | "edit";
  existing?: AnalyticalApplication | null;
}

function defaultGroupFor(analysisKey: string): string {
  return (
    getRegistryAnalysis(analysisKey)?.data_product_label || "Analyses"
  );
}

export default function CreateApplicationWizard({
  mode = "create",
  existing = null,
}: Props) {
  const router = useRouter();
  const productGroups = useMemo(() => groupRegistryByProduct(), []);
  const [step, setStep] = useState<Step>("name");
  const [name, setName] = useState(existing?.name || "");
  const [description, setDescription] = useState(
    existing?.description || ""
  );
  const [logo, setLogo] = useState<string | null>(
    existing?.icon || null
  );
  const [logoError, setLogoError] = useState<string | null>(null);
  const [selected, setSelected] = useState<string[]>(() => {
    if (existing?.analyses?.length) {
      return [...existing.analyses]
        .sort((a, b) => a.display_order - b.display_order)
        .map((row) => row.analysis_key);
    }
    return [];
  });
  const [groupByKey, setGroupByKey] = useState<Record<string, string>>(
    () => {
      const map: Record<string, string> = {};
      for (const row of existing?.analyses || []) {
        map[row.analysis_key] =
          row.navigation_group || defaultGroupFor(row.analysis_key);
      }
      return map;
    }
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const suggestedGroups = useMemo(() => {
    const labels = new Set<string>();
    for (const group of productGroups) {
      labels.add(group.data_product_label);
    }
    for (const value of Object.values(groupByKey)) {
      if (value.trim()) labels.add(value.trim());
    }
    return Array.from(labels);
  }, [productGroups, groupByKey]);

  function toggle(key: string) {
    setSelected((current) => {
      if (current.includes(key)) {
        setGroupByKey((groups) => {
          const next = { ...groups };
          delete next[key];
          return next;
        });
        return current.filter((item) => item !== key);
      }
      setGroupByKey((groups) => ({
        ...groups,
        [key]: groups[key] || defaultGroupFor(key),
      }));
      return [...current, key];
    });
  }

  function move(key: string, direction: -1 | 1) {
    setSelected((current) => {
      const index = current.indexOf(key);
      if (index < 0) return current;
      const next = index + direction;
      if (next < 0 || next >= current.length) return current;
      const copy = [...current];
      const [item] = copy.splice(index, 1);
      copy.splice(next, 0, item);
      return copy;
    });
  }

  function setGroup(key: string, group: string) {
    setGroupByKey((current) => ({ ...current, [key]: group }));
  }

  async function submit() {
    setSaving(true);
    setError(null);
    const analyses: AnalyticalApplicationAnalysis[] = selected.map(
      (analysis_key, display_order) => ({
        analysis_key,
        display_order,
        navigation_group:
          groupByKey[analysis_key]?.trim() ||
          defaultGroupFor(analysis_key),
      })
    );
    try {
      if (mode === "edit" && existing) {
        const updated = await updateAnalyticalApplication(existing.id, {
          name: name.trim(),
          description: description.trim(),
          icon: logo,
          analyses,
        });
        router.push(`/applications/${updated.id}`);
        return;
      }
      const created = await createAnalyticalApplication({
        name: name.trim(),
        description: description.trim(),
        icon: logo,
        analyses,
      });
      router.push(`/applications/${created.id}`);
    } catch (err) {
      setError(
        err instanceof Error
          ? err.message
          : "Unable to save application."
      );
    } finally {
      setSaving(false);
    }
  }

  const stepMeta =
    step === "name"
      ? {
          eyebrow: "01 — Identity",
          title: "Name your application",
          support: "Assemble the analyses you need into one focused workspace.",
        }
      : step === "select"
        ? {
            eyebrow: "02 — Analyses",
            title: "Select analytical capabilities",
            support:
              "Choose the analyses you want available in this application.",
          }
        : {
            eyebrow: "03 — Organize",
            title: "Arrange your workspace",
            support:
              "Set navigation order and groups. Groups default to the source data product.",
          };

  return (
    <div className="mx-auto max-w-3xl space-y-8 px-6 py-8 lg:px-8 lg:py-10">
      <div className="flex items-center justify-between">
        <Link
          href="/applications"
          className="text-sm transition-colors"
          style={{ color: appTheme.slate }}
        >
          ← Applications
        </Link>
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.2em]"
          style={{ color: appTheme.cyan }}
        >
          InsightPilot
        </p>
      </div>

      <header>
        <p
          className="text-[11px] font-semibold uppercase tracking-[0.18em]"
          style={{ color: appTheme.cyan }}
        >
          {mode === "edit" ? "Edit application" : "Create Analytical Application"}
        </p>
        <p
          className="mt-3 text-xs font-semibold uppercase tracking-[0.14em]"
          style={{ color: appTheme.slate }}
        >
          {stepMeta.eyebrow}
        </p>
        <h1
          className="ip-heading mt-2 text-3xl font-semibold tracking-tight"
          style={{ color: appTheme.white }}
        >
          {stepMeta.title}
        </h1>
        <p className="mt-2 text-sm" style={{ color: appTheme.silver }}>
          {stepMeta.support}
        </p>
      </header>

      <div className="flex gap-3 text-xs font-medium uppercase tracking-wide">
        {(["name", "select", "organize"] as Step[]).map((item, index) => (
          <span
            key={item}
            style={{
              color: step === item ? appTheme.cyan : appTheme.slate,
            }}
          >
            {String(index + 1).padStart(2, "0")} {item}
          </span>
        ))}
      </div>

      {step === "name" ? (
        <div className="ip-app-panel space-y-4 rounded-2xl p-6">
          <label className="block">
            <span
              className="text-sm font-medium"
              style={{ color: appTheme.white }}
            >
              Application name
            </span>
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="NFL Player Decision Center"
              className="ip-app-input mt-1.5 w-full rounded-lg px-3 py-2 text-sm"
            />
          </label>
          <label className="block">
            <span
              className="text-sm font-medium"
              style={{ color: appTheme.white }}
            >
              Description{" "}
              <span style={{ color: appTheme.slate }}>(optional)</span>
            </span>
            <textarea
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="A complete workspace for evaluating NFL players."
              rows={3}
              className="ip-app-input mt-1.5 w-full rounded-lg px-3 py-2 text-sm"
            />
          </label>

          <div>
            <span
              className="text-sm font-medium"
              style={{ color: appTheme.white }}
            >
              Logo{" "}
              <span style={{ color: appTheme.slate }}>(optional)</span>
            </span>
            <div className="mt-2 flex flex-wrap items-center gap-4">
              <ApplicationLogo src={logo} name={name || "Application"} size={48} />
              <div className="flex flex-wrap items-center gap-2">
                <label
                  className="cursor-pointer rounded-lg px-3 py-1.5 text-sm font-medium"
                  style={{
                    color: appTheme.white,
                    background: appTheme.deepBlue,
                    border: `1px solid ${appTheme.border}`,
                  }}
                >
                  Upload logo
                  <input
                    type="file"
                    accept="image/png,image/jpeg,image/webp,image/svg+xml"
                    className="hidden"
                    onChange={(event) => {
                      const file = event.target.files?.[0];
                      event.target.value = "";
                      if (!file) return;
                      void (async () => {
                        try {
                          setLogoError(null);
                          const dataUrl = await fileToLogoDataUrl(file);
                          setLogo(dataUrl);
                        } catch (err) {
                          setLogoError(
                            err instanceof Error
                              ? err.message
                              : "Unable to upload logo."
                          );
                        }
                      })();
                    }}
                  />
                </label>
                {logo ? (
                  <button
                    type="button"
                    className="rounded-lg px-3 py-1.5 text-sm"
                    style={{ color: appTheme.slate }}
                    onClick={() => {
                      setLogo(null);
                      setLogoError(null);
                    }}
                  >
                    Remove
                  </button>
                ) : null}
              </div>
            </div>
            <p className="mt-2 text-xs" style={{ color: appTheme.slate }}>
              Shown in the application header. PNG, JPG, WebP, or SVG.
            </p>
            {logoError ? (
              <p className="mt-1 text-xs" style={{ color: appTheme.negative }}>
                {logoError}
              </p>
            ) : null}
          </div>

          <div className="flex justify-end">
            <button
              type="button"
              disabled={!name.trim()}
              onClick={() => setStep("select")}
              className="ip-app-cta rounded-lg px-4 py-2 text-sm disabled:cursor-not-allowed"
            >
              Continue
            </button>
          </div>
        </div>
      ) : null}

      {step === "select" ? (
        <div className="space-y-5">
          {productGroups.map((group) => (
            <section
              key={group.data_product_id}
              className="ip-app-panel rounded-2xl p-6"
            >
              <h2
                className="text-lg font-semibold"
                style={{ color: appTheme.white }}
              >
                {group.data_product_label}
              </h2>
              <ul className="mt-4 space-y-2">
                {group.analyses.map((analysis) => {
                  const checked = selected.includes(analysis.analysis_key);
                  return (
                    <li key={analysis.analysis_key}>
                      <label
                        className="flex cursor-pointer gap-3 rounded-xl p-3 transition-colors"
                        style={{
                          background: checked
                            ? "rgba(0,140,255,0.10)"
                            : "transparent",
                          border: `1px solid ${
                            checked
                              ? appTheme.borderActive
                              : "transparent"
                          }`,
                        }}
                      >
                        <input
                          type="checkbox"
                          checked={checked}
                          onChange={() => toggle(analysis.analysis_key)}
                          className="mt-1 accent-[#00E5FF]"
                        />
                        <span>
                          <span
                            className="block text-sm font-semibold"
                            style={{ color: appTheme.white }}
                          >
                            {analysis.name}
                          </span>
                          <span
                            className="mt-0.5 block text-sm"
                            style={{ color: appTheme.silver }}
                          >
                            {analysis.description}
                          </span>
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            </section>
          ))}

          <aside
            className="rounded-2xl p-5"
            style={{
              background: appTheme.panel,
              border: `1px solid ${appTheme.border}`,
            }}
          >
            <h3
              className="text-sm font-semibold"
              style={{ color: appTheme.white }}
            >
              Selected Analyses
            </h3>
            {selected.length === 0 ? (
              <p className="mt-2 text-sm" style={{ color: appTheme.slate }}>
                No analyses selected yet.
              </p>
            ) : (
              <ol
                className="mt-3 list-decimal space-y-1 pl-5 text-sm"
                style={{ color: appTheme.silver }}
              >
                {selected.map((key) => (
                  <li
                    key={key}
                    className="flex items-center justify-between gap-2"
                  >
                    <span>{getRegistryAnalysis(key)?.name || key}</span>
                    <button
                      type="button"
                      className="text-xs"
                      style={{ color: appTheme.slate }}
                      onClick={() => toggle(key)}
                    >
                      Remove
                    </button>
                  </li>
                ))}
              </ol>
            )}
          </aside>

          <div className="flex justify-between">
            <GhostButton onClick={() => setStep("name")}>Back</GhostButton>
            <button
              type="button"
              disabled={selected.length === 0}
              onClick={() => setStep("organize")}
              className="ip-app-cta rounded-lg px-4 py-2 text-sm disabled:cursor-not-allowed"
            >
              Continue
            </button>
          </div>
        </div>
      ) : null}

      {step === "organize" ? (
        <div className="space-y-5">
          <section className="ip-app-panel rounded-2xl p-6">
            <h2
              className="text-lg font-semibold"
              style={{ color: appTheme.white }}
            >
              Application Navigation
            </h2>
            <p className="mt-1 text-sm" style={{ color: appTheme.silver }}>
              Order analyses and assign navigation groups.
            </p>
            <ul className="mt-4 space-y-3">
              {selected.map((key, index) => {
                const meta = getRegistryAnalysis(key);
                const groupValue =
                  groupByKey[key] || defaultGroupFor(key);
                return (
                  <li
                    key={key}
                    className="rounded-xl px-4 py-3"
                    style={{
                      background: appTheme.elevated,
                      border: `1px solid ${appTheme.border}`,
                    }}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <p
                          className="text-sm font-medium"
                          style={{ color: appTheme.white }}
                        >
                          {meta?.name || key}
                        </p>
                        <p
                          className="text-xs"
                          style={{ color: appTheme.slate }}
                        >
                          Source: {meta?.data_product_label}
                        </p>
                      </div>
                      <div className="flex gap-1">
                        <SmallBtn
                          disabled={index === 0}
                          onClick={() => move(key, -1)}
                        >
                          ↑
                        </SmallBtn>
                        <SmallBtn
                          disabled={index === selected.length - 1}
                          onClick={() => move(key, 1)}
                        >
                          ↓
                        </SmallBtn>
                      </div>
                    </div>
                    <label className="mt-3 block">
                      <span
                        className="text-xs font-medium uppercase tracking-wide"
                        style={{ color: appTheme.slate }}
                      >
                        Navigation group
                      </span>
                      <input
                        list={`nav-groups-${key}`}
                        value={groupValue}
                        onChange={(event) =>
                          setGroup(key, event.target.value)
                        }
                        className="ip-app-input mt-1 w-full max-w-sm rounded-lg px-3 py-1.5 text-sm"
                      />
                      <datalist id={`nav-groups-${key}`}>
                        {suggestedGroups.map((label) => (
                          <option key={label} value={label} />
                        ))}
                      </datalist>
                    </label>
                  </li>
                );
              })}
            </ul>
          </section>

          {error ? (
            <p className="text-sm" style={{ color: appTheme.negative }}>
              {error}
            </p>
          ) : null}

          <div className="flex justify-between">
            <GhostButton onClick={() => setStep("select")}>Back</GhostButton>
            <button
              type="button"
              disabled={saving || !name.trim() || selected.length === 0}
              onClick={() => void submit()}
              className="ip-app-cta rounded-lg px-4 py-2 text-sm disabled:cursor-not-allowed"
            >
              {saving
                ? "Launching…"
                : mode === "edit"
                  ? "Save Application"
                  : "Launch Application"}
            </button>
          </div>
          <p className="text-xs" style={{ color: appTheme.slate }}>
            {ANALYSIS_REGISTRY.length} analyses available in the registry.
          </p>
        </div>
      ) : null}
    </div>
  );
}

function GhostButton({
  children,
  onClick,
}: {
  children: React.ReactNode;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg px-4 py-2 text-sm font-medium transition-colors"
      style={{
        color: appTheme.silver,
        border: `1px solid ${appTheme.border}`,
      }}
    >
      {children}
    </button>
  );
}

function SmallBtn({
  children,
  onClick,
  disabled,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled?: boolean;
}) {
  return (
    <button
      type="button"
      disabled={disabled}
      onClick={onClick}
      className="rounded px-2 py-1 text-xs disabled:opacity-30"
      style={{
        color: appTheme.silver,
        border: `1px solid ${appTheme.border}`,
      }}
    >
      {children}
    </button>
  );
}
