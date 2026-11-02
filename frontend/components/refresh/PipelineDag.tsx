import Link from "next/link";

import type { RefreshPipeline } from "@/lib/refreshJobs";

interface PipelineDagProps {
  pipeline: RefreshPipeline;
  /** Stage ids highlighted as part of the active/selected job. */
  activeStages?: string[];
  compact?: boolean;
}

/**
 * Horizontal DAG of source → pipeline stages → dependent products.
 */
export default function PipelineDag({
  pipeline,
  activeStages,
  compact = false,
}: PipelineDagProps) {
  const highlight = new Set(activeStages ?? []);
  const hasHighlight = highlight.size > 0;

  return (
    <div className={compact ? "overflow-x-auto" : "overflow-x-auto pb-1"}>
      <div
        className={
          "flex min-w-max items-stretch gap-0 "
          + (compact ? "py-1" : "py-2")
        }
      >
        <DagNode
          title={pipeline.source}
          subtitle="source"
          tone="source"
          compact={compact}
        />
        <DagEdge />
        {pipeline.stages.map((stage, index) => (
          <div key={stage.id} className="flex items-stretch">
            <DagNode
              title={stage.label}
              subtitle={
                stage.tables.length
                  ? `${stage.tables.length} table${
                    stage.tables.length === 1 ? "" : "s"
                  }`
                  : undefined
              }
              tables={compact ? undefined : stage.tables}
              tone={
                !hasHighlight
                  ? "stage"
                  : highlight.has(stage.id)
                    ? "active"
                    : "muted"
              }
              compact={compact}
            />
            {index < pipeline.stages.length - 1 ? <DagEdge /> : null}
          </div>
        ))}
        <DagEdge />
        <div className="flex items-center gap-2">
          {pipeline.products.map((product) => (
            <DagNode
              key={product.id}
              title={product.name}
              subtitle="product"
              tone="product"
              compact={compact}
              href={product.href}
            />
          ))}
        </div>
      </div>
    </div>
  );
}

function DagEdge() {
  return (
    <div
      className="mx-1 flex w-6 shrink-0 items-center self-center sm:w-8"
      aria-hidden
    >
      <div className="h-px w-full bg-gray-300" />
      <div className="h-0 w-0 border-y-[4px] border-y-transparent border-l-[6px] border-l-gray-300" />
    </div>
  );
}

function DagNode({
  title,
  subtitle,
  tables,
  tone,
  compact,
  href,
}: {
  title: string;
  subtitle?: string;
  tables?: string[];
  tone: "source" | "stage" | "active" | "muted" | "product";
  compact: boolean;
  href?: string;
}) {
  const toneClass = {
    source: "border-sky-200 bg-sky-50 text-sky-950",
    stage: "border-gray-200 bg-white text-gray-900",
    active: "border-emerald-300 bg-emerald-50 text-emerald-950 ring-1 ring-emerald-200",
    muted: "border-gray-100 bg-gray-50 text-gray-400",
    product: "border-amber-200 bg-amber-50 text-amber-950",
  }[tone];

  const body = (
    <>
      <p
        className={
          "font-semibold leading-tight "
          + (compact ? "text-xs" : "text-sm")
        }
      >
        {title}
      </p>
      {subtitle ? (
        <p className="mt-0.5 text-[10px] uppercase tracking-wide opacity-70">
          {subtitle}
        </p>
      ) : null}
      {tables && tables.length > 0 && !compact ? (
        <ul className="mt-2 max-w-[9.5rem] space-y-0.5 text-[11px] leading-snug opacity-80">
          {tables.slice(0, 4).map((table) => (
            <li key={table} className="truncate font-mono">
              {table}
            </li>
          ))}
          {tables.length > 4 ? (
            <li className="opacity-70">+{tables.length - 4} more</li>
          ) : null}
        </ul>
      ) : null}
    </>
  );

  const className =
    "block shrink-0 rounded-lg border px-3 py-2 transition-colors "
    + toneClass
    + (compact ? " min-w-[5.5rem]" : " min-w-[7.5rem]")
    + (href ? " hover:brightness-[0.98]" : "");

  if (href) {
    return (
      <Link href={href} className={className}>
        {body}
      </Link>
    );
  }

  return <div className={className}>{body}</div>;
}
