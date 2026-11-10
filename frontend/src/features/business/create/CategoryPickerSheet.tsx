import { useEffect, useMemo, useState } from "react";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Spinner } from "@/components/ui/button";
import { SearchIcon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
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

interface SubcategorySearchItem extends Subcategory {
  category: {
    id: number;
    slug: string;
    name: string;
    icon: string;
  };
}

function normalize(value: string): string {
  return value
    .toLowerCase()
    .replace(/[يى]/g, "ی")
    .replace(/ك/g, "ک")
    .replace(/[\u200c\s]+/g, " ")
    .trim();
}

function includesQuery(query: string, ...values: Array<string | null | undefined>): boolean {
  if (!query) return true;
  return values.some((value) => value && normalize(value).includes(query));
}

function Chevron() {
  return (
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
  );
}

export function CategoryPickerSheet({
  open,
  onClose,
  selected,
  selectedSubcategory,
  onSelect,
}: CategoryPickerSheetProps) {
  const [active, setActive] = useState<Category | null>(null);
  const [query, setQuery] = useState("");

  useEffect(() => {
    if (!open) {
      setActive(null);
      setQuery("");
    }
  }, [open]);

  const categories = useApi<{ items: Category[] }>(["categories"], "/categories", {
    enabled: open,
  });
  const allSubcategories = useApi<{ items: SubcategorySearchItem[] }>(
    ["categories", "all-subcategories"],
    "/categories/subcategories",
    { enabled: open },
  );

  const categoryItems = categories.data?.items ?? [];
  const subcategoryItems = allSubcategories.data?.items ?? [];
  const normalizedQuery = normalize(query);

  const matchingCategories = useMemo(
    () =>
      categoryItems.filter((category) =>
        includesQuery(normalizedQuery, category.name, category.slug),
      ),
    [categoryItems, normalizedQuery],
  );

  const matchingSubcategories = useMemo(
    () =>
      subcategoryItems.filter((subcategory) =>
        includesQuery(
          normalizedQuery,
          subcategory.name,
          subcategory.category.name,
          ...subcategory.standard_tags,
        ),
      ),
    [normalizedQuery, subcategoryItems],
  );

  const activeSubcategories = useMemo(
    () => subcategoryItems.filter((subcategory) => subcategory.category_id === active?.id),
    [active?.id, subcategoryItems],
  );
  const visibleActiveSubcategories = normalizedQuery
    ? activeSubcategories.filter((subcategory) =>
        includesQuery(
          normalizedQuery,
          subcategory.name,
          ...subcategory.standard_tags,
        ),
      )
    : activeSubcategories;

  function choose(category: Category, subcategory: Subcategory | null) {
    onSelect(category, subcategory);
    onClose();
  }

  function categoryFor(item: SubcategorySearchItem): Category {
    return (
      categoryItems.find((category) => category.id === item.category.id) ?? {
        ...item.category,
        sort_order: 0,
        subcategory_count: 0,
      }
    );
  }

  function openCategory(category: Category) {
    setQuery("");
    setActive(category);
  }

  function goBack() {
    setQuery("");
    setActive(null);
  }

  const loading = categories.isLoading || allSubcategories.isLoading;
  const loadError = categories.error ?? allSubcategories.error;

  return (
    <BottomSheet open={open} onClose={onClose} title="انتخاب دسته‌بندی">
      <div className="mb-3">
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={active ? `جستجو در ${active.name}…` : "جستجوی دسته یا زیردسته…"}
            aria-label="جستجوی دسته‌بندی"
            className="h-11 pr-9 pl-9 text-sm"
            enterKeyHint="search"
          />
          {query && (
            <button
              type="button"
              aria-label="پاک کردن جستجو"
              onClick={() => setQuery("")}
              className="absolute left-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
            >
              ×
            </button>
          )}
        </div>
        {normalizedQuery && !active && (
          <p className="mt-1.5 text-[10px] text-slate-400">
            {matchingCategories.length + matchingSubcategories.length > 0
              ? "نتیجه‌ها در دسته‌ها و زیردسته‌ها"
              : "نتیجه‌ای پیدا نشد."}
          </p>
        )}
      </div>

      <div className="relative h-[54dvh] overflow-hidden">
        {/* Category list / global search results */}
        <div
          className={cn(
            "absolute inset-0 space-y-1 overflow-y-auto pb-4 transition-transform duration-300 ease-out",
            active ? "translate-x-full" : "translate-x-0",
          )}
          aria-hidden={active !== null}
        >
          {loading && (
            <div className="flex justify-center py-16 text-brand-600">
              <Spinner />
            </div>
          )}
          {loadError && (
            <p className="py-8 text-center text-sm text-rose-600">{errorMessage(loadError)}</p>
          )}

          {!loading && !loadError && normalizedQuery && (
            <>
              {matchingCategories.length > 0 && (
                <div>
                  <p className="px-1 pb-1 pt-2 text-[10px] font-bold text-slate-400">دسته‌ها</p>
                  {matchingCategories.map((category) => (
                    <button
                      key={`category-${category.id}`}
                      type="button"
                      onClick={() => openCategory(category)}
                      className="flex w-full items-center gap-3 rounded-xl px-3 py-2.5 text-right hover:bg-slate-50"
                    >
                      <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-lg">
                        {category.icon || "🏷️"}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="block truncate text-sm font-bold text-slate-900">
                          {category.name}
                        </span>
                        <span className="block text-[10px] text-slate-400">
                          {category.subcategory_count > 0
                            ? `${category.subcategory_count} زیردسته`
                            : "بدون زیردسته"}
                        </span>
                      </span>
                      <Chevron />
                    </button>
                  ))}
                </div>
              )}

              {matchingSubcategories.length > 0 && (
                <div>
                  <p className="px-1 pb-1 pt-2 text-[10px] font-bold text-slate-400">
                    زیردسته‌ها
                  </p>
                  {matchingSubcategories.map((subcategory) => (
                    <button
                      key={`subcategory-${subcategory.id}`}
                      type="button"
                      onClick={() => choose(categoryFor(subcategory), subcategory)}
                      className={cn(
                        "flex w-full items-center gap-3 rounded-xl border px-3 py-2.5 text-right transition-colors",
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
                        <span className="mt-0.5 block text-[10px] text-slate-400">
                          {subcategory.category.name}
                          {subcategory.standard_tags.length > 0
                            ? ` · ${subcategory.standard_tags.length} خدمت`
                            : ""}
                        </span>
                      </span>
                      <Chevron />
                    </button>
                  ))}
                </div>
              )}

              {matchingCategories.length === 0 && matchingSubcategories.length === 0 && (
                <div className="py-16 text-center">
                  <p className="text-2xl">🔍</p>
                  <p className="mt-2 text-sm font-bold text-slate-800">دسته‌ای پیدا نشد</p>
                  <p className="mt-1 text-[11px] text-slate-400">
                    نام دسته یا یکی از خدمات را جستجو کنید.
                  </p>
                </div>
              )}
            </>
          )}

          {!loading && !loadError && !normalizedQuery && (
            <>
              {categoryItems.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  onClick={() => openCategory(category)}
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
                  <Chevron />
                </button>
              ))}
            </>
          )}
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
              onClick={goBack}
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
            {loading && (
              <div className="flex justify-center py-10 text-brand-600">
                <Spinner />
              </div>
            )}
            {!loading && loadError && (
              <p className="py-6 text-center text-sm text-rose-600">{errorMessage(loadError)}</p>
            )}
            {!loading && !loadError && visibleActiveSubcategories.length === 0 && (
              <div className="py-6 text-center">
                <p className="text-sm text-slate-500">
                  {normalizedQuery ? "زیردسته‌ای پیدا نشد." : "این دسته زیردسته ندارد."}
                </p>
                {!normalizedQuery && active && (
                  <button
                    type="button"
                    onClick={() => choose(active, null)}
                    className="mt-3 rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white"
                  >
                    انتخاب همین دسته
                  </button>
                )}
              </div>
            )}
            {!loading && !loadError && visibleActiveSubcategories.map((subcategory) => (
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
                <Chevron />
              </button>
            ))}
          </div>
        </div>
      </div>
    </BottomSheet>
  );
}
