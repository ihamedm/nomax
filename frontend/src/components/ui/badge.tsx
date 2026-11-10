import type { ReactNode } from "react";

import { cn } from "@/lib/cn";

const ROLE_STYLES: Record<string, string> = {
  customer: "bg-slate-100 text-slate-600",
  owner: "bg-sky-100 text-sky-700",
  admin: "bg-amber-100 text-amber-700",
  superadmin: "bg-brand-100 text-brand-700",
};

const TONES: Record<string, string> = {
  slate: "bg-slate-100 text-slate-600",
  brand: "bg-brand-100 text-brand-700",
  amber: "bg-amber-100 text-amber-700",
  rose: "bg-rose-100 text-rose-700",
  sky: "bg-sky-100 text-sky-700",
};

export function RoleBadge({ role, label }: { role: string; label: string }) {
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-medium", ROLE_STYLES[role] ?? TONES.slate)}>
      {label}
    </span>
  );
}

export function Badge({
  children,
  tone = "slate",
  className,
}: {
  children: ReactNode;
  tone?: keyof typeof TONES;
  className?: string;
}) {
  return (
    <span
      className={cn(
        "inline-flex items-center rounded-full px-2.5 py-1 text-xs font-medium",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}
