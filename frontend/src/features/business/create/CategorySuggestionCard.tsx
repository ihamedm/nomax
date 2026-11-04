import { Button } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import type { CategorySuggestion } from "@/types";

interface CategorySuggestionCardProps {
  suggestions: CategorySuggestion[];
  autoApplied: boolean;
  onApply: (suggestion: CategorySuggestion) => void;
  onChange: () => void;
}

function SparkIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      aria-hidden
    >
      <path d="M12 3l1.4 4.1L17.5 8.5l-4.1 1.4L12 14l-1.4-4.1L6.5 8.5l4.1-1.4L12 3Z" />
      <path d="M18.5 14l.8 2.2 2.2.8-2.2.8-.8 2.2-.8-2.2-2.2-.8 2.2-.8.8-2.2Z" />
    </svg>
  );
}

export function CategorySuggestionCard({
  suggestions,
  autoApplied,
  onApply,
  onChange,
}: CategorySuggestionCardProps) {
  const visible = suggestions.filter((item) => item.quality !== "low");
  const primary = visible[0];
  if (!primary) return null;

  const alternatives = visible.slice(1);
  const path = primary.subcategory
    ? `${primary.category.name} > ${primary.subcategory.name}`
    : primary.category.name;

  return (
    <div
      className={cn(
        "mt-2 rounded-xl border p-3",
        autoApplied
          ? "border-brand-200 bg-brand-50/80"
          : "border-amber-200 bg-amber-50/70",
      )}
    >
      <div className="flex items-start gap-2.5">
        <span
          className={cn(
            "mt-0.5 flex h-8 w-8 shrink-0 items-center justify-center rounded-lg",
            autoApplied ? "bg-brand-100 text-brand-700" : "bg-amber-100 text-amber-700",
          )}
        >
          <SparkIcon />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex items-center gap-1.5">
            <p className="text-[11px] font-bold text-slate-700">پیشنهاد آزمایشی نومکس</p>
            <span className="rounded-full bg-white/80 px-1.5 py-0.5 text-[9px] font-medium text-slate-400">
              Laya
            </span>
          </div>
          <p className="mt-1 truncate text-sm font-black text-slate-900">{path}</p>
          <p className="mt-1 text-[10px] leading-4 text-slate-500">
            {primary.subcategory
              ? "این دسته و زیردسته بر اساس نام و توضیحات شما حدس زده شده است."
              : "دسته پیشنهاد شده است؛ زیردسته را خودتان انتخاب کنید."}
            {autoApplied ? " در صورت نادرست بودن، آن را تغییر دهید." : ""}
          </p>
        </div>
      </div>

      {!autoApplied && (
        <div className="mt-2.5 flex gap-2">
          <Button
            type="button"
            variant="outline"
            className="h-9 flex-1 text-xs"
            onClick={() => onApply(primary)}
          >
            انتخاب پیشنهاد
          </Button>
          <Button
            type="button"
            variant="ghost"
            className="h-9 text-xs"
            onClick={onChange}
          >
            خودم انتخاب می‌کنم
          </Button>
        </div>
      )}

      {autoApplied && (
        <button
          type="button"
          onClick={onChange}
          className="mt-2 text-[11px] font-bold text-brand-700 underline underline-offset-4"
        >
          تغییر دسته‌بندی
        </button>
      )}

      {alternatives.length > 0 && !autoApplied && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {alternatives.map((item) => (
            <button
              key={`${item.category.id}-${item.subcategory?.id ?? "category"}`}
              type="button"
              onClick={() => onApply(item)}
              className="rounded-full border border-amber-200 bg-white/80 px-2.5 py-1 text-[10px] font-medium text-amber-900 hover:border-amber-300"
            >
              {item.subcategory
                ? `${item.category.name} > ${item.subcategory.name}`
                : item.category.name}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
