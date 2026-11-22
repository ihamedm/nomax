import { useEffect, useMemo, useState } from "react";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button, Spinner } from "@/components/ui/button";
import { SearchIcon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/cn";
import { errorMessage } from "@/lib/api";
import { useApi } from "@/lib/query";
import { MAX_VISIBLE_TAGS } from "@/features/business/create/types";
import type { Category, Subcategory } from "@/types";

interface CategoryPickerSheetProps {
  open: boolean;
  onClose: () => void;
  selected: Category | null;
  selectedSubcategory?: Subcategory | null;
  onSelect: (category: Category, subcategory: Subcategory | null) => void;
  /** Multi-select: tapping subcategories toggles them, then one confirm. */
  multiple?: boolean;
  selectedSubcategories?: Subcategory[];
  onSelectMany?: (category: Category, subcategories: Subcategory[]) => void;
  /** Customers pick a parent category only; the subcategory panel is skipped. */
  categoriesOnly?: boolean;
}

interface SubcategorySearchItem extends Subcategory {
  category: {
    id: number;
    slug: string;
    name: string;
    icon: string;
  };
}

function visibleTagCount(subcategory: Subcategory): number {
  return (
    subcategory.visible_tags ?? subcategory.standard_tags.slice(0, MAX_VISIBLE_TAGS)
  ).length;
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

function PickedMark({ picked }: { picked: boolean }) {
  return (
    <span
      className={cn(
        "flex h-5 w-5 shrink-0 items-center justify-center rounded-md border text-[11px] font-bold",
        picked ? "border-brand-600 bg-brand-600 text-white" : "border-slate-300 text-transparent",
      )}
      aria-hidden
    >
      ✓
    </span>
  );
}

export function CategoryPickerSheet({
  open,
  onClose,
  selected,
  selectedSubcategory,
  onSelect,
  multiple = false,
  selectedSubcategories,
  onSelectMany,
  categoriesOnly = false,
}: CategoryPickerSheetProps) {
  const [active, setActive] = useState<Category | null>(null);
  const [query, setQuery] = useState("");
  const [draft, setDraft] = useState<Subcategory[]>([]);
  const [draftCategory, setDraftCategory] = useState<Category | null>(null);
  const [hint, setHint] = useState<string | null>(null);

  useEffect(() => {
    if (!open) {
      setActive(null);
      setQuery("");
      setHint(null);
      return;
    }
    if (multiple) {
      setDraft(selectedSubcategories ?? []);
      setDraftCategory((selectedSubcategories ?? []).length > 0 ? selected : null);
      setHint(null);
    }
    // Existing selection is only read when the sheet opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, multiple]);

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
    if (multiple) {
      if (subcategory === null) {
        setDraft([]);
        setDraftCategory(category);
        setHint(null);
      } else {
        toggle(category, subcategory);
      }
      return;
    }
    onSelect(category, subcategory);
    onClose();
  }

  function toggle(category: Category, subcategory: Subcategory) {
    if (draftCategory && draftCategory.id !== category.id) {
      setHint("همه زیردسته‌ها باید از یک دسته‌بندی باشند؛ ابتدا انتخاب‌های قبلی را بردارید.");
      return;
    }
    const picked = draft.some((item) => item.id === subcategory.id);
    const next = picked
      ? draft.filter((item) => item.id !== subcategory.id)
      : [...draft, subcategory];
    setDraft(next);
    setDraftCategory(next.length > 0 ? category : null);
    setHint(null);
  }

  function isPicked(subcategory: Subcategory): boolean {
    return multiple
      ? draft.some((item) => item.id === subcategory.id)
      : selectedSubcategory?.id === subcategory.id;
  }

  function confirmMultiple() {
    if (!draftCategory) return;
    onSelectMany?.(draftCategory, draft);
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
    if (categoriesOnly) {
      choose(category, null);
      return;
    }
    setActive(category);
  }

  function goBack() {
    setQuery("");
    setActive(null);
  }

  const loading = categories.isLoading || allSubcategories.isLoading;
  const loadError = categories.error ?? allSubcategories.error;
  const searchHitCount = categoriesOnly
    ? matchingCategories.length
    : matchingCategories.length + matchingSubcategories.length;
  const searchHitLabel = categoriesOnly ? "نتیجه‌ها در دسته‌ها" : "نتیجه‌ها در دسته‌ها و زیردسته‌ها";

  return (
    <BottomSheet open={open} onClose={onClose} title="انتخاب دسته‌بندی">
      <div className="mb-3">
        <div className="relative">
          <SearchIcon className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-slate-400" />
          <Input
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder={active ? `جستجو در ${active.name}…` : "جستجوی دسته‌بندی…"}
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
            {searchHitCount > 0 ? searchHitLabel : "نتیجه‌ای پیدا نشد."}
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
                        {!categoriesOnly && (
                          <span className="block text-[10px] text-slate-400">
                            {category.subcategory_count > 0
                              ? `${category.subcategory_count} زیردسته`
                              : "بدون زیردسته"}
                          </span>
                        )}
                      </span>
                      {!categoriesOnly && <Chevron />}
                    </button>
                  ))}
                </div>
              )}

              {!categoriesOnly && matchingSubcategories.length > 0 && (
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
                        isPicked(subcategory)
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
                          {visibleTagCount(subcategory) > 0
                            ? ` · ${visibleTagCount(subcategory)} خدمت`
                            : ""}
                        </span>
                      </span>
                      {multiple ? (
                        <PickedMark picked={isPicked(subcategory)} />
                      ) : (
                        <Chevron />
                      )}
                    </button>
                  ))}
                </div>
              )}

              {searchHitCount === 0 && (
                <div className="py-16 text-center">
                  <p className="text-2xl">🔍</p>
                  <p className="mt-2 text-sm font-bold text-slate-800">دسته‌ای پیدا نشد</p>
                  <p className="mt-1 text-[11px] text-slate-400">
                    {categoriesOnly
                      ? "نام دسته‌بندی را جستجو کنید."
                      : "نام دسته یا یکی از خدمات را جستجو کنید."}
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
                    selected?.id === category.id || (multiple && draftCategory?.id === category.id)
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
                    {!categoriesOnly && (
                      <span className="mt-0.5 block text-[11px] text-slate-400">
                        {category.subcategory_count > 0
                          ? `${category.subcategory_count} زیردسته`
                          : "بدون زیردسته"}
                      </span>
                    )}
                  </span>
                  {!categoriesOnly && <Chevron />}
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
                  isPicked(subcategory)
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
                  {visibleTagCount(subcategory) > 0 && (
                    <span className="mt-0.5 block text-[11px] text-slate-400">
                      {visibleTagCount(subcategory)} خدمت پیشنهادی
                    </span>
                  )}
                </span>
                {multiple ? (
                  <PickedMark picked={isPicked(subcategory)} />
                ) : (
                  <Chevron />
                )}
              </button>
            ))}
          </div>
        </div>
      </div>

      {multiple && (
        <div className="mt-3 space-y-2 border-t border-slate-100 pt-3">
          {hint && <p className="text-[11px] leading-5 text-rose-600">{hint}</p>}
          <div className="flex items-center justify-between gap-3">
            <span className="text-[11px] text-slate-500">
              {draftCategory
                ? draft.length > 0
                  ? `${draft.length} زیردسته انتخاب شد`
                  : "فقط همین دسته"
                : "زیردسته‌های کسب‌وکار را انتخاب کنید"}
            </span>
            <Button
              type="button"
              onClick={confirmMultiple}
              disabled={!draftCategory}
              className="min-w-24"
            >
              تأیید انتخاب
            </Button>
          </div>
        </div>
      )}
    </BottomSheet>
  );
}
