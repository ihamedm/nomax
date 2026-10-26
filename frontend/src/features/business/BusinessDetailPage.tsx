import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { api, errorMessage } from "@/lib/api";
import { fa, formatPhone, formatRating } from "@/lib/format";
import { NeshanMap, type MapMarker } from "@/features/map/NeshanMap";
import type { BusinessDetail } from "@/types";

function ActionLink({
  href,
  children,
  tone = "outline",
}: {
  href: string;
  children: ReactNode;
  tone?: "outline" | "primary";
}) {
  return (
    <a
      href={href}
      target={href.startsWith("tel:") ? undefined : "_blank"}
      rel={href.startsWith("tel:") ? undefined : "noreferrer"}
      className={
        tone === "primary"
          ? "inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 text-sm font-medium text-white"
          : "inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700"
      }
    >
      {children}
    </a>
  );
}

export function BusinessDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const [business, setBusiness] = useState<BusinessDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    let active = true;
    setLoading(true);
    setError(null);
    api<BusinessDetail>(`/businesses/${encodeURIComponent(slug)}`)
      .then((result) => {
        if (active) setBusiness(result);
      })
      .catch((loadError) => {
        if (active) setError(errorMessage(loadError));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [slug]);

  const mapMarkers = useMemo<MapMarker[]>(() => {
    if (!business?.geo) return [];
    return [
      {
        id: business.id,
        lat: business.geo.lat,
        lng: business.geo.lng,
        title: business.name,
        subtitle: business.address,
      },
    ];
  }, [business]);

  const instagramHandle = business?.instagram?.replace(/^@/, "").replace(/[^A-Za-z0-9._]/g, "");
  const callNumber = business?.phone_business
    ? `tel:0${business.phone_business.replace(/^0/, "")}`
    : null;
  const neshanLink = business?.geo
    ? `https://neshan.org/maps/@${business.geo.lat},${business.geo.lng},16z`
    : null;

  return (
    <main className="mx-auto min-h-[100dvh] w-full max-w-xl pb-16">
      <header className="sticky top-0 z-20 flex items-center gap-2 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
        <Link
          to="/search"
          aria-label="بازگشت به جستجو"
          className="flex h-9 w-9 items-center justify-center rounded-xl text-lg text-slate-500 hover:bg-slate-100"
        >
          →
        </Link>
        <p className="text-sm font-bold text-slate-800">جزئیات کسب‌وکار</p>
      </header>

      {loading && (
        <div className="flex justify-center py-24 text-brand-600">
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <div className="px-4 py-10">
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-sm text-rose-700">
            <p>{error}</p>
            <Link to="/search" className="mt-4 inline-block">
              <Button size="sm" variant="outline">
                بازگشت به جستجو
              </Button>
            </Link>
          </div>
        </div>
      )}

      {!loading && !error && business && (
        <div className="space-y-4 px-4 pt-4">
          <section className="overflow-hidden rounded-3xl bg-gradient-to-l from-brand-600 to-brand-500 p-5 text-white">
            <div className="flex items-start gap-4">
              <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white/15 text-4xl">
                {business.profile_image_url ? (
                  <img
                    src={business.profile_image_url}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span aria-hidden>{business.category?.icon ?? "🏪"}</span>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h1 className="text-xl font-black leading-8">{business.name}</h1>
                <p className="mt-1 text-xs text-white/75">
                  {business.category?.name}
                  {business.subcategory ? ` · ${business.subcategory.name}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {business.is_verified && (
                    <span className="rounded-full bg-white/15 px-2.5 py-1 text-[11px]">تأیید شده</span>
                  )}
                  {business.is_24h && (
                    <span className="rounded-full bg-amber-300/20 px-2.5 py-1 text-[11px] text-amber-100">
                      ۲۴ ساعته
                    </span>
                  )}
                </div>
              </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-white/85">{business.short_description}</p>

            <div className="mt-4 flex items-center justify-between rounded-2xl bg-white/10 px-4 py-3">
              <div>
                <p className="text-[11px] text-white/60">امتیاز کاربران</p>
                <p className="mt-1 text-lg font-black">
                  ★ {formatRating(business.rating_avg)}
                  <span className="mr-1 text-xs font-normal text-white/60">
                    از {fa(business.rating_count)} نظر
                  </span>
                </p>
              </div>
              <Badge tone="brand" className="bg-white/15 text-white">
                {business.rating_count > 0 ? "امتیاز ثبت‌شده" : "بدون نظر"}
              </Badge>
            </div>
          </section>

          <section className="grid grid-cols-2 gap-2">
            {callNumber ? (
              <ActionLink href={callNumber} tone="primary">
                📞 تماس با کسب‌وکار
              </ActionLink>
            ) : (
              <span className="inline-flex h-11 items-center justify-center rounded-xl bg-slate-100 text-xs text-slate-400">
                شماره تماس ثبت نشده
              </span>
            )}
            {neshanLink ? (
              <ActionLink href={neshanLink}>🧭 مسیریابی در نشان</ActionLink>
            ) : (
              <span className="inline-flex h-11 items-center justify-center rounded-xl bg-slate-100 text-xs text-slate-400">
                موقعیت ثبت نشده
              </span>
            )}
            {instagramHandle && (
              <ActionLink href={`https://instagram.com/${instagramHandle}`}>
                اینستاگرام @{instagramHandle}
              </ActionLink>
            )}
            {business.phone_business && (
              <div className="flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-600">
                <span dir="ltr">{formatPhone(business.phone_business)}</span>
              </div>
            )}
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-bold text-slate-900">درباره کسب‌وکار</h2>
            <p className="mt-2 text-xs leading-7 text-slate-600">
              {business.description || business.short_description}
            </p>
            <div className="mt-4 rounded-xl bg-slate-50 p-3">
              <p className="text-[11px] text-slate-400">آدرس</p>
              <p className="mt-1 text-xs leading-6 text-slate-700">{business.address}</p>
            </div>
          </section>

          {business.geo && (
            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-900">موقعیت روی نقشه</h2>
                {neshanLink && (
                  <a
                    href={neshanLink}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-brand-600"
                  >
                    باز کردن در نشان
                  </a>
                )}
              </div>
              <NeshanMap
                center={business.geo}
                markers={mapMarkers}
                zoom={15}
                fitToMarkers
                className="h-56"
              />
            </section>
          )}

          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between">
              <h2 className="text-sm font-bold text-slate-900">نظرات کاربران</h2>
              <span className="text-[11px] text-slate-400">فاز ۴</span>
            </div>
            <p className="mt-2 text-xs leading-6 text-slate-500">
              ثبت و نمایش نظرات پس از تأیید ادمین در فاز ۴ فعال می‌شود. امتیاز نمایش‌داده‌شده
              تا آن زمان از داده‌های نمونه است.
            </p>
          </section>
        </div>
      )}
    </main>
  );
}
