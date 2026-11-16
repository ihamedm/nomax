import { useEffect, useMemo, useRef, useState, type FormEvent } from "react";
import { keepPreviousData, useInfiniteQuery, useQuery } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button, Spinner } from "@/components/ui/button";
import { FilterIcon, LocationIcon } from "@/components/ui/icons";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, apiWithMeta, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fa } from "@/lib/format";
import { getCurrentPosition, geolocationNeedsPrompt } from "@/lib/geolocation";
import { useApi } from "@/lib/query";
import { BEHBAHAN_CENTER, DEFAULT_MAP_ZOOM, useUi } from "@/stores/ui";
import { BusinessCard } from "@/features/business/BusinessCard";
import { BEHBAHAN_BOUNDS, INITIAL_MAP_VIEWPORT } from "@/features/map/city";
import {
  buildClusterIndex,
  clusteredFeatures,
  clusterZoomTarget,
  isClusterFeature,
  pointMatchesFilters,
} from "@/features/map/clustering";
import { NeshanMap, type MapMarker, type MapViewport } from "@/features/map/NeshanMap";
import type { MapFeed, MapPoint } from "@/features/map/types";
import type {
  BusinessListItem,
  BusinessSort,
  Category,
  Coordinates,
  SearchMeta,
  Subcategory,
} from "@/types";

const SORT_OPTIONS: Array<{ value: BusinessSort; label: string; hint: string }> = [
  { value: "nearest", label: "نزدیکترین", hint: "نزدیکترین کسب‌وکارها اول فهرست می‌شوند" },
  { value: "top", label: "بهترین امتیاز", hint: "بیشترین امتیاز و تعداد نظر" },
  { value: "newest", label: "جدیدترین", hint: "تازه‌ترین کسب‌وکارهای تأییدشده" },
  { value: "urgent", label: "۲۴ ساعته", hint: "کسب‌وکارهای فعال در تمام ساعات" },
  { value: "visited", label: "پربازدیدترین", hint: "بیشترین بازدید صفحه کسب‌وکار" },
];

const RADIUS_OPTIONS = [2, 5, 10, 25];

function parseSort(value: string | null): BusinessSort {
  return SORT_OPTIONS.some((option) => option.value === value) ? (value as BusinessSort) : "nearest";
}

/** `null` means "no distance limit"; results are still ordered by distance. */
function parseRadius(value: string | null): number | null {
  const parsed = Number(value);
  return value && RADIUS_OPTIONS.includes(parsed) ? parsed : null;
}

/** Keep the map over Behbahan when the visitor shares a location elsewhere. */
function centerForLocation(location: Coordinates): Coordinates {
  const { west, south, east, north } = BEHBAHAN_BOUNDS;
  const inside =
    location.lng >= west && location.lng <= east && location.lat >= south && location.lat <= north;
  return inside ? location : BEHBAHAN_CENTER;
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
  const openLocationPrompt = useUi((state) => state.openLocationPrompt);
  const chromeHidden = useUi((state) => state.chromeHidden);
  const setChromeHidden = useUi((state) => state.setChromeHidden);

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
  const [selectedPoint, setSelectedPoint] = useState<MapPoint | null>(null);
  const [viewport, setViewport] = useState<MapViewport>(INITIAL_MAP_VIEWPORT);
  const [camera, setCamera] = useState<{ center: Coordinates; zoom: number } | null>(null);

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

  // Collapse the app chrome while reading results: hide on scroll down, bring
  // it back on scroll up (or at the very top). Reset when leaving the page.
  useEffect(() => {
    let lastY = window.scrollY;
    const onScroll = () => {
      const y = window.scrollY;
      // Wait until the results have scrolled past the header + search bar,
      // otherwise collapsing them would leave an empty band at the top.
      if (y <= 8) setChromeHidden(false);
      else if (y > 180 && y - lastY > 6) setChromeHidden(true);
      else if (lastY - y > 6) setChromeHidden(false);
      lastY = y;
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      setChromeHidden(false);
    };
  }, [setChromeHidden]);

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
        lat: String(location.lat),
        lng: String(location.lng),
      });
      if (radius !== null) search.set("radius_km", String(radius));
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

  // One cached snapshot, clustered in the browser. Panning and zooming only
  // re-query the local index, so the map never waits for the network mid-drag.
  const mapFeed = useQuery({
    queryKey: ["map", "snapshot", qParam],
    enabled: view === "map",
    // Cached snapshot is shown immediately; revalidate in the background after
    // five minutes so newly approved businesses appear without a reload.
    staleTime: 5 * 60 * 1000,
    gcTime: 24 * 60 * 60 * 1000,
    placeholderData: keepPreviousData,
    queryFn: () => {
      const search = new URLSearchParams();
      if (qParam) search.set("q", qParam);
      const query = search.toString();
      return api<MapFeed>(`/map/businesses${query ? `?${query}` : ""}`);
    },
  });

  const mapLoading = mapFeed.isFetching && !mapFeed.data;
  const loading = searchQuery.isLoading;
  const loadingMore = searchQuery.isFetchingNextPage;
  const hasMore = searchQuery.hasNextPage;
  const error = searchQuery.error ? errorMessage(searchQuery.error) : null;

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

  const mapPoints = useMemo(
    () =>
      (mapFeed.data?.items ?? []).filter((point) =>
        pointMatchesFilters(point, catParam, subcatParam),
      ),
    [mapFeed.data, catParam, subcatParam],
  );

  const mapIndex = useMemo(() => buildClusterIndex(mapPoints), [mapPoints]);

  const mapMarkers = useMemo<MapMarker[]>(() => {
    if (!mapIndex) return [];
    // At the deepest zooms the remaining waypoints are individual businesses.
    // Teardrops there turn a dense street into a wall of pins, so switch to
    // compact dots once the map is close enough to identify addresses.
    const compact = viewport.zoom >= 17;
    return clusteredFeatures(mapIndex, viewport).map((feature) => {
      const [lng, lat] = feature.geometry.coordinates;
      if (isClusterFeature(feature)) {
        const { cluster_id, point_count } = feature.properties;
        return {
          id: `cluster-${cluster_id}`,
          lat,
          lng,
          count: point_count,
          expansionZoom: mapIndex.getClusterExpansionZoom(cluster_id),
          title: `${fa(point_count)} کسب‌وکار`,
        };
      }
      const point = feature.properties as MapPoint;
      return {
        id: point.id,
        lat: point.lat,
        lng: point.lng,
        title: point.name,
        subtitle: point.address,
        compact,
      };
    });
  }, [mapIndex, viewport]);

  function handleMapMarker(marker: MapMarker) {
    if (marker.count !== undefined) {
      // viewport.zoom is the live map zoom (fractional). The old code mixed in
      // a stale camera zoom, so after panning it could zoom back out.
      const zoom = clusterZoomTarget(viewport.zoom, marker.expansionZoom);
      setCamera({ center: { lat: marker.lat, lng: marker.lng }, zoom });
      return;
    }
    const point = mapPoints.find((item) => item.id === marker.id);
    if (point) setSelectedPoint(point);
  }

  function pointAsListItem(point: MapPoint): BusinessListItem {
    return {
      id: point.id,
      slug: point.slug,
      name: point.name,
      short_description: "",
      address: point.address,
      category: point.category ?? null,
      subcategory: null,
      geo: { lat: point.lat, lng: point.lng },
      distance_m: null,
      rating_avg: point.rating_avg,
      rating_count: point.rating_count,
      like_count: point.like_count ?? 0,
      is_24h: point.is_24h,
      is_verified: point.is_verified,
      is_license_verified: point.is_license_verified ?? false,
      profile_image_url: point.profile_image_url ?? null,
      avatar_url: point.avatar_url ?? null,
    };
  }

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
    if (locationSource !== "gps" && (await geolocationNeedsPrompt())) {
      openLocationPrompt();
      return;
    }
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
      <section
        className={cn(
          "sticky top-14 z-20 border-b border-slate-200 bg-slate-50/95 px-4 pb-3 pt-3 backdrop-blur transition-transform duration-200",
          chromeHidden && "-translate-y-[calc(100%+3.5rem)]",
        )}
      >
        <form onSubmit={submitSearch} className="flex items-center gap-2">
          <div className="relative min-w-0 flex-1">
            <Input
              ref={searchInputRef}
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder="جستجوی نام، خدمت یا شماره…"
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
        </form>

        <div className="mt-3 flex items-center gap-2 overflow-x-auto pb-0.5">
          <button
            type="button"
            onClick={openFilters}
            className={cn(
              "flex shrink-0 items-center gap-1 rounded-full border px-3 py-1.5 text-[11px] font-medium",
              catParam ? "border-brand-200 bg-brand-50 text-brand-700" : "border-slate-200 text-slate-600",
            )}
          >
            <FilterIcon className="h-3.5 w-3.5" />
            فیلترها
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
            aria-label="موقعیت من"
            title="موقعیت من"
            className={cn(
              "flex shrink-0 items-center justify-center rounded-full border p-1.5 disabled:opacity-50",
              locationSource === "gps"
                ? "border-brand-200 bg-brand-50 text-brand-700"
                : "border-slate-200 text-slate-600",
            )}
          >
            {locating ? <Spinner /> : <LocationIcon className="h-4 w-4" />}
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

        {(qParam || catParam || subcatParam || radius !== null) && (
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
            {radius !== null && (
              <FilterChip
                label={`تا ${fa(radius)} کیلومتر`}
                onClear={() => updateParams({ radius: null })}
              />
            )}
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
            <div className="relative">
              <NeshanMap
                center={camera?.center ?? centerForLocation(location)}
                markers={mapMarkers}
                onMarkerClick={handleMapMarker}
                onViewportChange={setViewport}
                className="h-[55dvh]"
                zoom={camera?.zoom ?? DEFAULT_MAP_ZOOM}
              />
              {mapLoading && (
                <div className="pointer-events-none absolute inset-0 flex items-center justify-center rounded-2xl bg-white/60 text-brand-600 backdrop-blur-[1px]">
                  <Spinner />
                </div>
              )}
            </div>
          </div>
        ) : (
          <>
            <div className="mb-3">
              <p className="text-xs text-slate-500">
                {loading ? "در حال جستجو…" : `${fa(items.length)} نتیجه`}
              </p>
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
                  عبارت دیگری را امتحان کنید یا دسته‌بندی را تغییر دهید. محدودیت فاصله
                  به‌صورت پیش‌فرض غیرفعال است.
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
        open={selectedPoint !== null}
        title="کسب‌وکار روی نقشه"
        onClose={() => setSelectedPoint(null)}
      >
        {selectedPoint && (
          <div className="space-y-3">
            <BusinessCard business={pointAsListItem(selectedPoint)} />
            <p className="text-center text-[11px] text-slate-400">
              برای دیدن جزئیات، تصاویر و نظرات روی کارت بزنید.
            </p>
          </div>
        )}
      </BottomSheet>

      <BottomSheet
        open={filterOpen}
        title="دسته‌بندی و فاصله"
        onClose={() => setFilterOpen(false)}
        footer={
          <div className="flex gap-2">
            <Button className="flex-1" onClick={applyFilters}>
              اعمال فیلتر
            </Button>
            <Button variant="ghost" onClick={clearFilters}>
              حذف همه
            </Button>
          </div>
        }
      >
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
            <p className="mb-2 text-[11px] leading-5 text-slate-500">
              به‌طور پیش‌فرض محدودیتی روی فاصله اعمال نمی‌شود و نتایج همه شهر نمایش داده
              می‌شوند؛ نزدیک‌ترین کسب‌وکارها همیشه اول فهرست می‌آیند.
            </p>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                onClick={() => updateParams({ radius: null })}
                className={cn(
                  "rounded-full border px-3 py-1.5 text-[11px]",
                  radius === null
                    ? "border-brand-400 bg-brand-50 text-brand-700"
                    : "border-slate-200 text-slate-600",
                )}
              >
                بدون محدودیت فاصله
              </button>
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
