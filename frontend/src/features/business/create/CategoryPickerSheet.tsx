import { useEffect, useState } from "react";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Spinner } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/api";
import { useApi } from "@/lib/query";
import type { Category, Subcategory } from "@/types";

interface CategoryPickerSheetProps {
  open: boolean;
  onClose: () => void;
  selected: Category | null;
  selectedSubcategory?: Subcategory | null;
  onSelect: (category: Category, subcategory: Subcategory | null) => void;
}

export function CategoryPickerSheet({
  open,
  onClose,
  selected,
  selectedSubcategory,
  onSelect,
}: CategoryPickerSheetProps) {
  const [active, setActive] = useState<Category | null>(null);

  useEffect(() => {
    if (!open) setActive(null);
  }, [open]);

  const categories = useApi<{ items: Category[] }>(["categories"], "/categories", {
    enabled: open,
  });
  const subcategories = useApi<{ category: Category; items: Subcategory[] }>(
    ["categories", active?.id ?? 0, "subcategories"],
    `/categories/${active?.id ?? 0}/subcategories`,
    { enabled: open && active !== null },
  );

  function choose(category: Category, subcategory: Subcategory | null) {
    onSelect(category, subcategory);
    onClose();
  }

  return (
    <BottomSheet open={open} onClose={onClose} title="انتخاب دسته‌بندی">
      <div className="relative h-[58dvh] overflow-hidden">
        {/* Category list */}
        <div
          className={cn(
            "absolute inset-0 space-y-1 overflow-y-auto pb-4 transition-transform duration-300 ease-out",
            active ? "translate-x-full" : "translate-x-0",
          )}
          aria-hidden={active !== null}
        >
          {categories.isLoading && (
            <div className="flex justify-center py-16 text-brand-600">
              <Spinner />
            </div>
          )}
          {categories.error && (
            <p className="py-8 text-center text-sm text-rose-600">
              {errorMessage(categories.error)}
            </p>
          )}
          {categories.data?.items.map((category) => (
            <button
              key={category.id}
              type="button"
              onClick={() => setActive(category)}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-right transition-colors",
                selected?.id === category.id
                  ? "border-brand-200 bg-brand-50"
                  : "border-transparent hover:bg-slate-50",
              )}
            >
              <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-lg">
                {category.icon || "🏷️"}
              </span>
              <span className="min-w-0 flex-1">
                <span className="block truncate text-sm font-bold text-slate-900">
                  {category.name}
                </span>
                <span className="mt-0.5 block text-[11px] text-slate-400">
                  {category.subcategory_count > 0
                    ? `${category.subcategory_count} زیردسته`
                    : "بدون زیردسته"}
                </span>
              </span>
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.8"
                className="h-4 w-4 shrink-0 text-slate-400"
                aria-hidden
              >
                <path d="M15 5l-7 7 7 7" />
              </svg>
            </button>
          ))}
        </div>

        {/* Subcategory panel slides in from the left */}
        <div
          className={cn(
            "absolute inset-0 flex flex-col bg-white transition-transform duration-300 ease-out",
            active ? "translate-x-0" : "-translate-x-full",
          )}
          aria-hidden={active === null}
        >
          <div className="flex items-center gap-2 border-b border-slate-100 pb-2">
            <button
              type="button"
              onClick={() => setActive(null)}
              className="flex h-9 items-center gap-1 rounded-lg px-2 text-xs text-slate-500 hover:bg-slate-50"
            >
              <svg
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="2"
                className="h-4 w-4"
                aria-hidden
              >
                <path d="M9 5l7 7-7 7" />
              </svg>
              بازگشت
            </button>
            <p className="truncate text-sm font-bold text-slate-900">{active?.name}</p>
          </div>

          <div className="min-h-0 flex-1 space-y-1 overflow-y-auto py-2">
            {subcategories.isLoading && (
              <div className="flex justify-center py-10 text-brand-600">
                <Spinner />
              </div>
            )}
            {subcategories.error && (
              <p className="py-6 text-center text-sm text-rose-600">
                {errorMessage(subcategories.error)}
              </p>
            )}
            {active && subcategories.data?.items.length === 0 && (
              <div className="py-6 text-center">
                <p className="text-sm text-slate-500">این دسته زیردسته ندارد.</p>
                <button
                  type="button"
                  onClick={() => choose(active, null)}
                  className="mt-3 rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white"
                >
                  انتخاب همین دسته
                </button>
              </div>
            )}
            {subcategories.data?.items.map((subcategory) => (
              <button
                key={subcategory.id}
                type="button"
                onClick={() => active && choose(active, subcategory)}
                className={cn(
                  "flex w-full items-center gap-3 rounded-xl border px-3 py-3 text-right transition-colors",
                  selectedSubcategory?.id === subcategory.id
                    ? "border-brand-200 bg-brand-50"
                    : "border-transparent hover:bg-slate-50",
                )}
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-slate-100 text-base">
                  {subcategory.icon || "•"}
                </span>
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium text-slate-800">
                    {subcategory.name}
                  </span>
                  {subcategory.standard_tags.length > 0 && (
                    <span className="mt-0.5 block text-[11px] text-slate-400">
                      {subcategory.standard_tags.length} خدمت پیشنهادی
                    </span>
                  )}
                </span>
                <svg
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.8"
                  className="h-4 w-4 shrink-0 text-slate-300"
                  aria-hidden
                >
                  <path d="M15 5l-7 7 7 7" />
                </svg>
              </button>
            ))}
          </div>
        </div>
      </div>
    </BottomSheet>
  );
}
