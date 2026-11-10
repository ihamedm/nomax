import { useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { SearchIcon } from "@/components/ui/icons";
import { errorMessage } from "@/lib/api";
import { useApi } from "@/lib/query";
import { BusinessCard } from "@/features/business/BusinessCard";
import type { BusinessListItem, Category } from "@/types";

interface AdItem {
  id: string;
  title: string;
  body?: string | null;
  image_url?: string | null;
  target_url?: string | null;
}

function BannerAd({ ad }: { ad?: AdItem }) {
  if (ad?.image_url) {
    return (
      <a
        href={ad.target_url || "#"}
        className="block overflow-hidden rounded-2xl border border-slate-200 bg-white"
      >
        <img src={ad.image_url} alt={ad.title} className="h-28 w-full object-cover sm:h-36" />
      </a>
    );
  }
  return (
    <div className="flex h-24 items-center justify-between gap-4 rounded-2xl border border-dashed border-brand-200 bg-gradient-to-l from-brand-50 to-white px-5 sm:h-28">
      <div>
        <p className="text-xs font-bold text-brand-700">{ad?.title || "جایگاه بنر تبلیغاتی"}</p>
        <p className="mt-1 text-[11px] text-slate-400">
          {ad?.body || "این فضا برای بنر تبلیغاتی کسب‌وکارها رزرو شده است."}
        </p>
      </div>
      <span className="shrink-0 rounded-full bg-white px-3 py-1 text-[10px] font-bold text-brand-600 shadow-sm">
        تبلیغ
      </span>
    </div>
  );
}

function BusinessCarousel({
  title,
  href,
  items,
  loading,
  empty,
}: {
  title: string;
  href: string;
  items: BusinessListItem[];
  loading: boolean;
  empty: string;
}) {
  return (
    <section className="space-y-3">
      <div className="flex items-center justify-between">
        <h2 className="text-sm font-black text-slate-900">{title}</h2>
        <Link to={href} className="text-[11px] font-medium text-brand-600">
          مشاهده همه ←
        </Link>
      </div>
      {loading ? (
        <div className="flex gap-3 overflow-hidden">
          {[0, 1, 2].map((index) => (
            <div key={index} className="h-36 w-72 shrink-0 animate-pulse rounded-2xl bg-slate-100" />
          ))}
        </div>
      ) : items.length === 0 ? (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center text-xs text-slate-500">
          {empty}
        </p>
      ) : (
        <div className="flex snap-x snap-mandatory gap-3 overflow-x-auto pb-2 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden">
          {items.map((business) => (
            <div key={business.id} className="flex w-[300px] shrink-0 snap-start">
              <BusinessCard business={business} />
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

export function HomePage() {
  const navigate = useNavigate();
  const [searchTerm, setSearchTerm] = useState("");

  const categoriesQuery = useApi<{ items: Category[] }>(["categories"], "/categories");
  const trendingQuery = useApi<{ items: string[] }>(["search", "trending"], "/search/trending");
  const newestQuery = useApi<{ items: BusinessListItem[] }>(
    ["businesses", "newest"],
    "/businesses?sort=newest&limit=10",
  );
  const visitedQuery = useApi<{ items: BusinessListItem[] }>(
    ["businesses", "visited"],
    "/businesses?sort=visited&limit=10",
  );
  const adsQuery = useApi<{ items: AdItem[] }>(["ads"], "/ads");

  const categories = categoriesQuery.data?.items ?? [];
  const ads = adsQuery.data?.items ?? [];
  const homeBanner = ads[0];

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    const term = searchTerm.trim();
    navigate(term ? `/search?q=${encodeURIComponent(term)}&focus=1` : "/search?focus=1");
  }

  return (
    <main className="mx-auto w-full max-w-5xl px-4 pb-10 pt-4">
      <section className="relative overflow-hidden rounded-3xl bg-gradient-to-bl from-brand-700 via-brand-600 to-brand-500 px-5 py-8 text-white sm:px-8 sm:py-10">
        <div className="pointer-events-none absolute -left-16 -top-16 h-48 w-48 rounded-full bg-white/10" />
        <div className="pointer-events-none absolute -bottom-20 right-10 h-52 w-52 rounded-full bg-white/10" />
        <div className="relative">
          <p className="text-[11px] text-white/70">بازار محلی بهبهان</p>
          <h1 className="mt-2 max-w-xl text-2xl font-black leading-relaxed sm:text-3xl">
            کسب‌وکار مورد نظرت رو راحت‌تر پیدا کن
          </h1>
          <form onSubmit={submitSearch} className="mt-5 flex max-w-2xl gap-2">
            <Input
              value={searchTerm}
              onChange={(event) => setSearchTerm(event.target.value)}
              onFocus={() => navigate("/search?focus=1")}
              placeholder="چه خدمتی لازم داری؟"
              aria-label="جستجوی کسب‌وکار"
              enterKeyHint="search"
              className="h-12 border-white/20 bg-white/15 text-white placeholder:text-white/70 focus:border-white focus:ring-white/30"
            />
            <Button
              type="submit"
              size="lg"
              aria-label="جستجو"
              className="hero-search-action w-12 shrink-0 bg-white px-0 text-brand-700 hover:bg-white/90"
            >
              <SearchIcon />
            </Button>
          </form>
          <div className="mt-3 flex flex-wrap gap-2">
            {(trendingQuery.data?.items ?? []).slice(0, 5).map((term) => (
              <Link
                key={term}
                to={`/search?q=${encodeURIComponent(term)}&focus=1`}
                className="rounded-full bg-white/15 px-3 py-1 text-[11px] text-white/90 hover:bg-white/25"
              >
                {term}
              </Link>
            ))}
          </div>
        </div>
      </section>

      <div className="mt-4">
        <BannerAd ad={homeBanner} />
      </div>

      <section className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-black text-slate-900">دسته‌بندی‌ها</h2>
          <Link to="/categories" className="text-[11px] font-medium text-brand-600">
            مشاهده همه ←
          </Link>
        </div>

        {categoriesQuery.isLoading ? (
          <div className="grid grid-cols-3 gap-2">
            {[0, 1, 2, 3, 4, 5].map((index) => (
              <div key={index} className="h-24 animate-pulse rounded-2xl bg-slate-100" />
            ))}
          </div>
        ) : categoriesQuery.error ? (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
            <p>{errorMessage(categoriesQuery.error)}</p>
            <Button
              size="sm"
              variant="outline"
              className="mt-3"
              onClick={() => void categoriesQuery.refetch()}
            >
              تلاش دوباره
            </Button>
          </div>
        ) : (
          <div className="grid grid-cols-3 gap-2 sm:gap-3">
            {categories.slice(0, 9).map((category) => (
              <Link
                key={category.id}
                to={`/search?cat=${category.slug}`}
                className="flex min-h-24 flex-col items-center justify-center gap-1.5 rounded-2xl border border-slate-200 bg-white px-2 py-3 text-center transition-colors hover:border-brand-300 hover:bg-brand-50/40"
              >
                <span className="text-2xl" aria-hidden>
                  {category.icon}
                </span>
                <span className="line-clamp-1 text-xs font-bold text-slate-800">
                  {category.name}
                </span>
              </Link>
            ))}
          </div>
        )}

        <Link to="/categories" className="mt-3 block">
          <Button variant="outline" className="w-full">
            مشاهده همه دسته‌بندی‌ها
          </Button>
        </Link>
      </section>

      <div className="mt-6">
        <BannerAd ad={ads.find((ad) => ad.id !== homeBanner?.id)} />
      </div>

      <div className="mt-6 space-y-6">
        <BusinessCarousel
          title="کسب‌وکارهای تازه"
          href="/search?sort=newest"
          items={newestQuery.data?.items ?? []}
          loading={newestQuery.isLoading}
          empty="هنوز کسب‌وکار تازه‌ای ثبت نشده است."
        />
        <BusinessCarousel
          title="پربازدیدترین کسب‌وکارها"
          href="/search?sort=visited"
          items={visitedQuery.data?.items ?? []}
          loading={visitedQuery.isLoading}
          empty="هنوز بازدیدی ثبت نشده است."
        />
      </div>

      <div className="mt-6">
        <BannerAd />
      </div>
    </main>
  );
}
