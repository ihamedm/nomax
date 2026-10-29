import { cn } from "@/lib/cn";

export function RatingStars({
  rating,
  size = "sm",
  className,
}: {
  rating: number;
  size?: "xs" | "sm" | "md";
  className?: string;
}) {
  const sizeClass = size === "xs" ? "text-[11px]" : size === "md" ? "text-base" : "text-xs";
  return (
    <span
      className={cn("inline-flex items-center gap-0.5 leading-none", sizeClass, className)}
      aria-label={`${rating} از ۵ ستاره`}
    >
      {[1, 2, 3, 4, 5].map((value) => (
        <span key={value} aria-hidden className={value <= rating ? "text-amber-500" : "text-slate-300"}>
          ★
        </span>
      ))}
    </span>
  );
}
