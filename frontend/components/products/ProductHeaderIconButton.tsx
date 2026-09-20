"use client";

import {
  LucideIcon,
  Loader2,
} from "lucide-react";

import {
  Button,
} from "@/components/ui/button";

import {
  cn,
} from "@/lib/utils";


interface Props {
  label: string;
  icon: LucideIcon;
  onClick?: () => void;
  disabled?: boolean;
  loading?: boolean;
  variant?: "outline" | "default";
  className?: string;
}


export default function ProductHeaderIconButton({
  label,
  icon: Icon,
  onClick,
  disabled = false,
  loading = false,
  variant = "outline",
  className,
}: Props) {

  return (
    <Button
      type="button"
      variant={variant}
      size="icon-sm"
      title={label}
      aria-label={label}
      onClick={onClick}
      disabled={disabled || loading}
      className={cn(className)}
    >

      {loading ? (

        <Loader2
          className="animate-spin"
          aria-hidden
        />

      ) : (

        <Icon aria-hidden />

      )}

    </Button>

  );

}
