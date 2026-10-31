import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { useInfiniteQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button, Spinner } from "@/components/ui/button";
import { SearchIcon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { apiWithMeta, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fa } from "@/lib/format";
import { getCurrentPosition } from "@/lib/geolocation";
import { useApi } from "@/lib/query";
import { useUi } from "@/stores/ui";
import { BusinessCard } from "@/features/business/BusinessCard";
import { NeshanMap, type MapMarker } from "@/features/map/NeshanMap";
import type {
  BusinessListItem,
  BusinessSort,
  Category,
  SearchMeta,
  Subcategory,
} from "@/types";

const SORT_OPTIONS: Array<{ value: BusinessSort; label: string; hint: string }> = [
  { value: "nearest", label: "نزدیک‌ترین", hint: "نزدیک‌ترین کسب‌وکارها به موقعیت شما" },
  { value: "top", label: "بهترین امتیاز", hint: "بیشترین امتیاز و تعداد نظر" },
  { value: "newest", label: "جدیدترین", hint: "تازه‌ترین کسب‌وکارهای تأییدشده" },
  { value: "urgent", label: "۲۴ ساعته", hint: "کسب‌وکارهای فعال در تمام ساعات" },
  { value: "visited", label: "پربازدیدترین", hint: "بیشترین بازدید صفحه کسب‌وکار" },
];

const RADIUS_OPTIONS = [2, 5, 10, 25];

function parseSort(value: string | null): BusinessSort {
  return SORT_OPTIONS.some((option) => option.value === value) ? (value as BusinessSort) : "nearest";
}

function parseRadius(value: string | null): number {
  const parsed = Number(value);
  return RADIUS_OPTIONS.includes(parsed) ? parsed : 10;
}

function FilterChip({ label, onClear }: { label: string; onClear: () => void }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-3 py-1 text-[11px] text-brand-700">
      {label}
      <button type="button" aria-label={`حذف ${label}`} onClick={onClear} className="text-brand-500">
        ×
      </button>
    </span>
  );
}

export function SearchPage() {
  const [params, setParams] = useSearchParams();
  const toast = useToast();
  const location = useUi((state) => state.location);
  const locationSource = useUi((state) => state.locationSource);
  const setLocation = useUi((state) => state.setLocation);

  const qParam = params.get("q")?.trim() ?? "";
  const catParam = params.get("cat") ?? "";
  const subcatParam = params.get("subcat") ?? "";
  const sort = parseSort(params.get("sort"));
  const radius = parseRadius(params.get("radius"));

  const [query, setQuery] = useState(qParam);
  const searchInputRef = useRef<HTMLInputElement | null>(null);
  const focusParam = params.get("focus");
  const categoriesQuery = useApi<{ items: Category[] }>(["categories"], "/categories");
  const categories = categoriesQuery.data?.items ?? [];
  const trendingQuery = useApi<{ items: string[] }>(["search", "trending"], "/search/trending");

  const [view, setView] = useState<"list" | "map">("list");
  const [selectedBusinessId, setSelectedBusinessId] = useState<string | null>(null);

  const [locating, setLocating] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const [sortOpen, setSortOpen] = useState(false);
  const [draftCat, setDraftCat] = useState(catParam);
  const [draftSubcat, setDraftSubcat] = useState(subcatParam);

  const sentinelRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    setQuery(qParam);
  }, [qParam]);

  useEffect(() => {
    if (focusParam) searchInputRef.current?.focus();
  }, [focusParam]);

  // Opening the search page always puts the cursor in the field. A short wait
  // lets the shell mount and the mobile keyboard target the right element.
  useEffect(() => {
    // The tiny delay also covers cold-load hydration.
    const timer = window.setTimeout(() => {
      searchInputRef.current?.focus({ preventScroll: true });
    }, 80);
    return () => window.clearTimeout(timer);
  }, []);

  // Debounce typing into the URL query. A request is made only after the user
  // pauses, instead of on every keystroke.
  useEffect(() => {
    const term = query.trim();
    if (term === qParam) return;
    const timer = window.setTimeout(() => {
      updateParams({ q: term || null });
    }, 450);
    return () => window.clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query, qParam]);

  const selectedCategory = categories.find((category) => category.slug === catParam);
  const activeSubcategoriesQuery = useApi<{ items: Subcategory[] }>(
    ["subcategories", selectedCategory?.id],
    `/categories/${selectedCategory?.id}/subcategories`,
    { enabled: Boolean(selectedCategory) },
  );
  const activeSubcategories = activeSubcategoriesQuery.data?.items ?? [];

  const draftCategory = categories.find((category) => category.slug === draftCat);
  const sheetSubcategoriesQuery = useApi<{ items: Subcategory[] }>(
    ["subcategories", draftCategory?.id],
    `/categories/${draftCategory?.id}/subcategories`,
    { enabled: Boolean(draftCategory) },
  );
  const sheetSubcategories = sheetSubcategoriesQuery.data?.items ?? [];

  const searchQuery = useInfiniteQuery({
    queryKey: ["businesses", { q: qParam, cat: catParam, subcat: subcatParam, sort, radius, lat: location.lat, lng: location.lng }],
    queryFn: async ({ pageParam }) => {
      const search = new URLSearchParams({
        limit: "12",
        sort,
        radius_km: String(radius),
        lat: String(location.lat),
        lng: String(location.lng),
      });
      if (qParam) search.set("q", qParam);
      if (catParam) search.set("cat", catParam);
      if (subcatParam) search.set("subcat", subcatParam);
      if (pageParam) search.set("cursor", pageParam);
      return apiWithMeta<{ items: BusinessListItem[] }, SearchMeta>(`/businesses?${search.toString()}`);
    },
    initialPageParam: null as string | null,
    getNextPageParam: (lastPage) => lastPage.meta?.next_cursor ?? null,
  });

  const items = useMemo(
    () => searchQuery.data?.pages.flatMap((page) => page.data.items) ?? [],
    [searchQuery.data],
  );
  const loading = searchQuery.isLoading;
  const loadingMore = searchQuery.isFetchingNextPage;
  const hasMore = searchQuery.hasNextPage;
  const error = searchQuery.error ? errorMessage(searchQuery.error) : null;
  const selectedBusiness = selectedBusinessId
    ? items.find((business) => business.id === selectedBusinessId) ?? null
    : null;

  useEffect(() => {
    const sentinel = sentinelRef.current;
    if (!sentinel || !hasMore || loading || loadingMore) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries[0]?.isIntersecting) void searchQuery.fetchNextPage();
      },
      { rootMargin: "320px" },
    );
    observer.observe(sentinel);
    return () => observer.disconnect();
  }, [hasMore, loading, loadingMore, searchQuery]);

  const activeSubcategoryName =
    activeSubcategories.find((subcategory) => subcategory.slug === subcatParam)?.name ?? subcatParam;

  const sortLabel = SORT_OPTIONS.find((option) => option.value === sort)?.label ?? "";

  const mapMarkers = useMemo<MapMarker[]>(
    () =>
      items
        .filter((business) => business.geo)
        .map((business) => ({
          id: business.id,
          lat: business.geo!.lat,
          lng: business.geo!.lng,
          title: business.name,
          subtitle: business.address,
        })),
    [items],
  );

  function updateParams(patch: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    setParams(next, { replace: true });
  }

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    updateParams({ q: query.trim() });
  }

  function openFilters() {
    setDraftCat(catParam);
    setDraftSubcat(subcatParam);
    setFilterOpen(true);
  }

  function applyFilters() {
    updateParams({ cat: draftCat, subcat: draftSubcat });
    setFilterOpen(false);
  }

  function clearFilters() {
    setDraftCat("");
    setDraftSubcat("");
    updateParams({ cat: null, subcat: null });
    setFilterOpen(false);
  }

  async function locateMe() {
    setLocating(true);
    try {
      const coords = await getCurrentPosition();
      setLocation(coords);
      toast("موقعیت شما اعمال شد.");
    } catch {
      toast("دسترسی به موقعیت ممکن نشد؛ مرکز بهبهان استفاده می‌شود.");
    } finally {
      setLocating(false);
    }
  }

  return (
    <main className="mx-auto w-full max-w-5xl pb-10">
      <section className="sticky top-14 z-20 border-b border-slate-200 bg-slate-50/95 px-4 pb-3 pt-3 backdrop-blur">
        <form onSubmit={submitSearch} className="flex items-center gap-2">
          <div className="relative min-w-0 flex-1">
            <Input
              ref={searchInputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="جستجوی کسب‌وکار یا خدمت…"
              aria-label="جستجوی کسب‌وکار"
              className="h-11 pl-9 text-sm"
              enterKeyHint="search"
              inputMode="search"
              autoFocus
            />
            {query && (
              <button
                type="button"
                aria-label="پاک کردن جستجو"
                onClick={() => {
                  setQuery("");
                  updateParams({ q: null });
                  searchInputRef.current?.focus();
                }}
                className="absolute left-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-full text-slate-400 hover:bg-slate-100 hover:text-slate-700"
              >
                ×
              </button>
            )}
          </div>
          <Button
            type="submit"
            size="sm"
            aria-label="جستجو"
            className="h-11 w-11 shrink-0 px-0"
          >
            <SearchIcon />
          </Button>
        </form>

        <div className="mt-3 flex items-center gap-2 overflow-x-auto pb-0.5">
          <button
            type="button"
            onClick={openFilters}
            className={cn(
              "shrink-0 rounded-full border px-3 py-1.5 text-[11px] font-medium",
              catParam ? "border-brand-200 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-600",
            )}
          >
            دسته‌بندی
            {catParam ? " ●" : ""}
          </button>
          <button
            type="button"
            onClick={() => setSortOpen(true)}
            className="shrink-0 rounded-full border border-slate-200 px-3 py-1.5 text-[11px] font-medium text-slate-600"
          >
            {sortLabel}
          </button>
          <button
            type="button"
            onClick={() => void locateMe()}
            disabled={locating}
            className="shrink-0 rounded-full border border-slate-200 px-3 py-1.5 text-[11px] font-medium text-slate-600 disabled:opacity-50"
          >
            {locating ? "در حال یافتن…" : locationSource === "gps" ? "موقعیت من ✓" : "موقعیت من"}
          </button>
          <div className="mr-auto flex shrink-0 rounded-full bg-slate-100 p-1">
            <button
              type="button"
              onClick={() => setView("list")}
              className={cn(
                "rounded-full px-3 py-1 text-[11px]",
                view === "list" ? "bg-white font-bold text-slate-900 shadow-sm" : "text-slate-500",
              )}
            >
              فهرست
            </button>
            <button
              type="button"
              onClick={() => setView("map")}
              className={cn(
                "rounded-full px-3 py-1 text-[11px]",
                view === "map" ? "bg-white font-bold text-slate-900 shadow-sm" : "text-slate-500",
              )}
            >
              نقشه
            </button>
          </div>
        </div>

        {(qParam || catParam || subcatParam) && (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {qParam && <FilterChip label={`جستجو: ${qParam}`} onClear={() => updateParams({ q: null })} />}
            {catParam && (
              <FilterChip
                label={selectedCategory?.name ?? catParam}
                onClear={() => updateParams({ cat: null, subcat: null })}
              />
            )}
            {subcatParam && (
              <FilterChip label={activeSubcategoryName} onClear={() => updateParams({ subcat: null })} />
            )}
            <FilterChip label={`تا ${fa(radius)} کیلومتر`} onClear={() => updateParams({ radius: null })} />
          </div>
        )}
      </section>

      {!qParam && !catParam && !subcatParam && (
        <section className="px-4 pt-4">
          <p className="text-xs font-bold text-slate-500">جستجوهای پرطرفدار</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {(trendingQuery.data?.items ?? []).map((term) => (
              <Link
                key={term}
                to={`/search?q=${encodeURIComponent(term)}&focus=1`}
                className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs text-slate-600 hover:border-brand-300 hover:text-brand-700"
              >
                {term}
              </Link>
            ))}
          </div>
        </section>
      )}

      <section className="px-4 py-4">
        {view === "map" ? (
          <div className="space-y-3">
            <NeshanMap
              center={location}
              markers={mapMarkers}
              fitToMarkers
              onMarkerClick={(marker) => setSelectedBusinessId(marker.id)}
              className="h-[55dvh]"
              zoom={13}
            />
            <p className="text-center text-[11px] text-slate-400">
              {fa(items.length)} کسب‌وکار روی نقشه نمایش داده می‌شود. برای دیدن اطلاعات، روی
              نشان هر کسب‌وکار بزنید.
            </p>
          </div>
        ) : (
          <>
            <div className="mb-3 flex items-center justify-between">
              <p className="text-xs text-slate-500">
                {loading ? "در حال جستجو…" : `${fa(items.length)} نتیجه`}
              </p>
              {hasMore && <span className="text-[11px] text-slate-400">نتایج بیشتر در راه است</span>}
            </div>

            {loading && (
              <div className="space-y-3">
                {[0, 1, 2].map((index) => (
                  <div key={index} className="h-32 animate-pulse rounded-2xl bg-slate-100" />
                ))}
              </div>
            )}

            {!loading && error && (
              <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
                <p>{error}</p>
                <Button size="sm" variant="outline" className="mt-3" onClick={() => void searchQuery.refetch()}>
                  تلاش دوباره
                </Button>
              </div>
            )}

            {!loading && !error && items.length === 0 && (
              <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
                <p className="text-2xl">🔍</p>
                <p className="mt-3 text-sm font-bold text-slate-900">نتیجه‌ای پیدا نشد</p>
                <p className="mt-1 text-xs leading-6 text-slate-500">
                  عبارت دیگری را امتحان کنید یا فیلترها و محدوده فاصله را تغییر دهید.
                </p>
                <Button size="sm" variant="outline" className="mt-4" onClick={clearFilters}>
                  حذف فیلترها
                </Button>
              </div>
            )}

            {!loading && !error && items.length > 0 && (
              <div className="grid gap-3 md:grid-cols-2">
                {items.map((business) => (
                  <BusinessCard key={business.id} business={business} />
                ))}
              </div>
            )}

            <div ref={sentinelRef} className="h-4" />
            {loadingMore && (
              <div className="flex justify-center py-4 text-brand-600">
                <Spinner />
              </div>
            )}
          </>
        )}
      </section>

      <BottomSheet
        open={selectedBusiness !== null}
        title="کسب‌وکار روی نقشه"
        onClose={() => setSelectedBusinessId(null)}
      >
        {selectedBusiness && (
          <div className="space-y-3">
            <BusinessCard business={selectedBusiness} />
            <p className="text-center text-[11px] text-slate-400">
              برای دیدن جزئیات، تصاویر و نظرات روی کارت بزنید.
            </p>
          </div>
        )}
      </BottomSheet>

      <BottomSheet open={filterOpen} title="دسته‌بندی و فاصله" onClose={() => setFilterOpen(false)}>
        <div className="space-y-5">
          <div>
            <p className="mb-2 text-xs font-bold text-slate-400">دسته‌بندی</p>
            <div className="grid grid-cols-2 gap-2">
              <button
                type="button"
                onClick={() => {
                  setDraftCat("");
                  setDraftSubcat("");
                }}
                className={cn(
                  "rounded-xl border px-3 py-2 text-xs",
                  draftCat === "" ? "border-brand-400 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-600",
                )}
              >
                همه دسته‌ها
              </button>
              {categories.map((category) => (
                <button
                  key={category.id}
                  type="button"
                  onClick={() => {
                    setDraftCat(category.slug);
                    setDraftSubcat("");
                  }}
                  className={cn(
                    "rounded-xl border px-3 py-2 text-right text-xs",
                    draftCat === category.slug
                      ? "border-brand-400 bg-brand-50 text-brand-700"
                      : "border-slate-200 text-slate-600",
                  )}
                >
                  <span aria-hidden className="ml-1">
                    {category.icon}
                  </span>
                  {category.name}
                </button>
              ))}
            </div>
          </div>

          {draftCat && sheetSubcategories.length > 0 && (
            <div>
              <p className="mb-2 text-xs font-bold text-slate-400">زیردسته</p>
              <div className="flex flex-wrap gap-2">
                <button
                  type="button"
                  onClick={() => setDraftSubcat("")}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-[11px]",
                    draftSubcat === ""
                      ? "border-brand-400 bg-brand-50 text-brand-700"
                      : "border-slate-200 text-slate-600",
                  )}
                >
                  همه زیردسته‌ها
                </button>
                {sheetSubcategories.map((subcategory) => (
                  <button
                    key={subcategory.id}
                    type="button"
                    onClick={() => setDraftSubcat(subcategory.slug)}
                    className={cn(
                      "rounded-full border px-3 py-1.5 text-[11px]",
                      draftSubcat === subcategory.slug
                        ? "border-brand-400 bg-brand-50 text-brand-700"
                        : "border-slate-200 text-slate-600",
                    )}
                  >
                    {subcategory.name}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <p className="mb-2 text-xs font-bold text-slate-400">حداکثر فاصله</p>
            <div className="flex flex-wrap gap-2">
              {RADIUS_OPTIONS.map((option) => (
                <button
                  key={option}
                  type="button"
                  onClick={() => updateParams({ radius: String(option) })}
                  className={cn(
                    "rounded-full border px-3 py-1.5 text-[11px]",
                    radius === option
                      ? "border-brand-400 bg-brand-50 text-brand-700"
                      : "border-slate-200 text-slate-600",
                  )}
                >
                  تا {fa(option)} کیلومتر
                </button>
              ))}
            </div>
          </div>

          <div className="flex gap-2">
            <Button className="flex-1" onClick={applyFilters}>
              اعمال فیلتر
            </Button>
            <Button variant="ghost" onClick={clearFilters}>
              حذف همه
            </Button>
          </div>
        </div>
      </BottomSheet>

      <BottomSheet open={sortOpen} title="مرتب‌سازی" onClose={() => setSortOpen(false)}>
        <div className="space-y-2">
          {SORT_OPTIONS.map((option) => (
            <button
              key={option.value}
              type="button"
              onClick={() => {
                updateParams({ sort: option.value === "nearest" ? null : option.value });
                setSortOpen(false);
              }}
              className={cn(
                "flex w-full items-start justify-between rounded-xl border px-4 py-3 text-right",
                sort === option.value ? "border-brand-400 bg-brand-50" : "border-slate-200",
              )}
            >
              <span>
                <span className="block text-sm font-bold text-slate-800">{option.label}</span>
                <span className="mt-1 block text-[11px] text-slate-500">{option.hint}</span>
              </span>
              {sort === option.value && <Badge tone="brand">انتخاب‌شده</Badge>}
            </button>
          ))}
        </div>
      </BottomSheet>
    </main>
  );
}
