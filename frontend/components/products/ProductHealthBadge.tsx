"use client";

import {
  useState,
} from "react";

import {
  DataProduct,
  ProductHealth,
} from "@/types/report";

import {
  HEALTH_STYLES,
  resolveProductHealth,
} from "@/lib/productHealth";


interface ProductHealthProduct {
  health?: DataProduct["health"];
  status: DataProduct["status"];
  coverage: DataProduct["coverage"];
  insights?: DataProduct["insights"];
  change_summary?: DataProduct["change_summary"];
  metadata?: DataProduct["metadata"];
  dashboards?: DataProduct["dashboards"];
}


interface Props {
  product: ProductHealthProduct;
  showLabel?: boolean;
  showPopover?: boolean;
  popoverSize?: "compact" | "full";
  align?: "left" | "right";
  className?: string;
}


const CHECK_ITEMS = [
  {
    key: "required_fields_present",
    label: "Required fields present",
  },
  {
    key: "data_quality_acceptable",
    label: "Data quality acceptable",
  },
  {
    key: "no_major_anomalies",
    label: "No major anomalies",
  },
  {
    key: "product_generated_successfully",
    label: "Product generated successfully",
  },
] as const;


export default function ProductHealthBadge({
  product,
  showLabel = true,
  showPopover = false,
  popoverSize = "compact",
  align = "right",
  className = "",
}: Props) {

  const [
    open,
    setOpen,
  ] = useState(false);

  const health =
    resolveProductHealth(product);

  const styles =
    HEALTH_STYLES[health.status];


  const trigger = showLabel ? (

    <span
      className={`inline-flex items-center gap-2 rounded-full px-3 py-1 text-xs font-medium ring-1 ring-inset ${styles.badge} ${className}`}
    >

      <span
        className={`h-2 w-2 rounded-full ${styles.dot}`}
        aria-hidden
      />

      {health.label}

    </span>

  ) : (

    <span
      className={`inline-flex h-3.5 w-3.5 shrink-0 items-center justify-center rounded-full ring-2 ring-white ${styles.dot} ${className}`}
      aria-hidden
    />

  );


  if (!showPopover) {

    return (
      <span
        className={showLabel ? undefined : "inline-flex"}
        title={health.summary}
      >
        {trigger}
      </span>
    );

  }


  return (
    <div
      className="relative inline-flex"
      onMouseEnter={() =>
        setOpen(true)
      }
      onMouseLeave={() =>
        setOpen(false)
      }
      onFocus={() =>
        setOpen(true)
      }
      onBlur={() =>
        setOpen(false)
      }
    >

      <button
        type="button"
        className={`inline-flex cursor-default items-center rounded-full focus:outline-none focus-visible:ring-2 focus-visible:ring-gray-400 ${
          showLabel ? "" : "p-0.5"
        }`}
        aria-label={`${health.label} product health`}
        aria-expanded={open}
      >
        {trigger}
      </button>


      {open && (

        <div
          className={`absolute top-full z-50 mt-2 w-80 rounded-xl border bg-white shadow-lg ${
            align === "right"
              ? "right-0"
              : "left-0"
          } ${
            popoverSize === "full"
              ? "w-[min(36rem,calc(100vw-2rem))]"
              : ""
          }`}
          role="tooltip"
        >

          <HealthPopoverContent
            health={health}
            size={popoverSize}
          />

        </div>

      )}

    </div>

  );

}


function HealthPopoverContent({
  health,
  size,
}: {
  health: ProductHealth;
  size: "compact" | "full";
}) {

  const styles =
    HEALTH_STYLES[health.status];


  if (size === "compact") {

    return (
      <div className={`rounded-xl p-4 ${styles.panel}`}>

        <div className="flex items-center gap-2">

          <span
            className={`h-2.5 w-2.5 rounded-full ${styles.dot}`}
          />

          <p className="text-sm font-semibold text-gray-950">
            {health.label}
          </p>

        </div>

        <p className="mt-2 text-sm leading-6 text-gray-700">
          {health.summary}
        </p>

        {health.reasons.length > 0 && (

          <ul className="mt-3 space-y-1.5">

            {health.reasons.map(
              (reason, index) => (

                <li
                  key={`${reason}-${index}`}
                  className="text-sm leading-6 text-gray-700"
                >
                  • {reason}
                </li>

              )
            )}

          </ul>

        )}

      </div>
    );

  }


  return (
    <div className={`overflow-hidden rounded-xl ${styles.panel}`}>

      <div className="border-b border-black/5 px-5 py-4">

        <div className="flex items-center gap-2">

          <span
            className={`h-2.5 w-2.5 rounded-full ${styles.dot}`}
          />

          <h3 className="text-base font-semibold text-gray-950">
            Product Health
          </h3>

          <span className="text-sm font-medium text-gray-700">
            {health.label}
          </span>

        </div>

        <p className="mt-2 text-sm leading-6 text-gray-700">
          {health.summary}
        </p>

      </div>


      <div className="grid gap-5 px-5 py-4 sm:grid-cols-2">

        <div>

          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Health checks
          </p>

          <ul className="mt-3 space-y-2">

            {CHECK_ITEMS.map(
              (item) => {

                const passed =
                  health.checks?.[
                    item.key
                  ] ?? false;

                return (
                  <li
                    key={item.key}
                    className="flex items-center gap-2 text-sm text-gray-800"
                  >

                    <span
                      className={`flex h-5 w-5 items-center justify-center rounded-full text-xs font-semibold ${
                        passed
                          ? "bg-green-600 text-white"
                          : "bg-gray-300 text-gray-700"
                      }`}
                    >
                      {passed ? "✓" : "!"}
                    </span>

                    {item.label}

                  </li>
                );

              }
            )}

          </ul>

        </div>


        <div>

          <p className="text-xs font-semibold uppercase tracking-wide text-gray-500">
            Notes
          </p>

          <ul className="mt-3 space-y-2">

            {health.reasons.map(
              (reason, index) => (

                <li
                  key={`${reason}-${index}`}
                  className="text-sm leading-6 text-gray-700"
                >
                  • {reason}
                </li>

              )
            )}

          </ul>

        </div>

      </div>

    </div>

  );

}


interface PanelProps {
  product: ProductHealthProduct;
  embedded?: boolean;
}


export function ProductHealthPanel({
  product,
  embedded = false,
}: PanelProps) {

  const health =
    resolveProductHealth(product);

  const styles =
    HEALTH_STYLES[health.status];


  return (
    <section
      className={`overflow-hidden rounded-2xl border shadow-sm ${styles.panel} ${
        embedded ? "" : "mt-8"
      }`}
    >

      <HealthPopoverContent
        health={health}
        size="full"
      />

    </section>

  );

}
