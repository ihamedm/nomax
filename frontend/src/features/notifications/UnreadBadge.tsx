import { cn } from "@/lib/cn";

/** Small red counter shown on the header user icon and the profile card. */
export function UnreadBadge({
  count,
  className,
  label,
}: {
  count: number;
  className?: string;
  label?: string;
}) {
  if (count <= 0) return null;
  const visual = count > 99 ? "۹۹+" : count.toLocaleString("fa-IR");
  return (
    <span
      aria-label={label ?? `${count.toLocaleString("fa-IR")} پیام خوانده‌نشده`}
      className={cn(
        "pointer-events-none absolute -left-1 -top-1 flex h-5 min-w-5 items-center justify-center rounded-full bg-rose-500 px-1 text-[10px] font-bold leading-none text-white ring-2 ring-white dark:ring-slate-900",
        className,
      )}
    >
      {visual}
    </span>
  );
}
