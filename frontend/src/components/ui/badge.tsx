import { cn } from "@/lib/cn";

const STYLES: Record<string, string> = {
  customer: "bg-slate-100 text-slate-600",
  owner: "bg-sky-100 text-sky-700",
  admin: "bg-amber-100 text-amber-700",
  superadmin: "bg-brand-100 text-brand-700",
};

export function RoleBadge({ role, label }: { role: string; label: string }) {
  return (
    <span className={cn("rounded-full px-2.5 py-1 text-xs font-medium", STYLES[role] ?? STYLES.customer)}>
      {label}
    </span>
  );
}
