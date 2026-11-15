import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { fa, formatDistance, formatRating } from "@/lib/format";
import type { BusinessListItem } from "@/types";

function LicenseTick() {
  return (
    <svg
      viewBox="0 0 24 24"
      className="h-3.5 w-3.5 shrink-0 text-sky-500"
      role="img"
      aria-label="مجوز تأیید شده"
    >
      <path
        fill="currentColor"
        d="M12 2a10 10 0 1 0 0 20 10 10 0 0 0 0-20Zm-1.1 14.3-3.6-3.6 1.4-1.4 2.2 2.2 4.8-4.8 1.4 1.4-6.2 6.2Z"
      />
    </svg>
  );
}

export function BusinessCard({ business }: { business: BusinessListItem }) {
  const avatar = business.avatar_url || business.profile_image_url;
  const subcategories = business.subcategories?.length
    ? business.subcategories
    : business.subcategory
      ? [business.subcategory]
      : [];
  return (
    <Link
      to={`/businesses/${business.slug}`}
      className="flex h-full w-full flex-col rounded-2xl border border-slate-200 bg-white p-4 transition-colors hover:border-brand-300 active:bg-brand-50/40"
    >
      <div className="flex gap-3">
        <div className="flex w-16 shrink-0 flex-col items-center">
          <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full border-2 border-slate-200 bg-brand-50 text-2xl">
            {avatar ? (
              <img src={avatar} alt="" className="h-full w-full object-cover" loading="lazy" />
            ) : (
              <span aria-hidden>{business.category?.icon ?? "🏪"}</span>
            )}
          </div>
          {business.is_verified && (
            <span className="mt-1 whitespace-nowrap rounded-full bg-brand-600 px-1.5 py-0.5 text-[7px] font-bold leading-3 text-white shadow-sm">
              تایید هویت شده
            </span>
          )}
          {business.rating_count > 0 && (
            <span className="mt-1.5 inline-flex items-center gap-0.5 whitespace-nowrap rounded-lg bg-amber-50 px-1.5 py-0.5 text-[11px] font-bold text-amber-700">
              ★ {formatRating(business.rating_avg)}
              <span className="font-normal text-amber-500">({fa(business.rating_count)})</span>
            </span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="flex min-w-0 items-center gap-1 text-sm font-bold text-slate-900">
              <span className="truncate">{business.name}</span>
              {business.is_license_verified && <LicenseTick />}
            </h3>
          </div>

          <p className="mt-0.5 text-[11px] text-slate-400">
            {business.category?.name ?? "دسته‌بندی نشده"}
            {subcategories.map((item) => ` · ${item.name}`).join("")}
          </p>

          <p className="mt-1 line-clamp-1 text-xs text-slate-500">{business.short_description}</p>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {business.is_24h && <Badge tone="amber">۲۴ ساعته</Badge>}
            {business.like_count > 0 && <Badge tone="rose">♥ {fa(business.like_count)}</Badge>}
            {business.distance_m !== null && (
              <Badge tone="slate">{formatDistance(business.distance_m)}</Badge>
            )}
          </div>

          <p className="mt-2 line-clamp-1 text-[11px] text-slate-400">{business.address}</p>

          {business.bookmark_note && (
            <p className="mt-2 line-clamp-3 rounded-lg bg-amber-50 px-2 py-1 text-[11px] leading-5 text-amber-800">
              📝 {business.bookmark_note}
            </p>
          )}
        </div>
      </div>
    </Link>
  );
}
