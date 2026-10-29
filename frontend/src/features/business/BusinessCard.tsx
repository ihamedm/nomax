import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { fa, formatDistance, formatRating } from "@/lib/format";
import type { BusinessListItem } from "@/types";

export function BusinessCard({ business }: { business: BusinessListItem }) {
  return (
    <Link
      to={`/businesses/${business.slug}`}
      className="flex h-full w-full flex-col rounded-2xl border border-slate-200 bg-white p-4 transition-colors hover:border-brand-300 active:bg-brand-50/40"
    >
      <div className="flex gap-3">
        <div className="flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-brand-50 text-2xl">
          {business.profile_image_url ? (
            <img
              src={business.profile_image_url}
              alt=""
              className="h-full w-full object-cover"
              loading="lazy"
            />
          ) : (
            <span aria-hidden>{business.category?.icon ?? "🏪"}</span>
          )}
        </div>

        <div className="min-w-0 flex-1">
          <div className="flex items-start justify-between gap-2">
            <h3 className="truncate text-sm font-bold text-slate-900">{business.name}</h3>
            {business.rating_count > 0 && (
              <span className="shrink-0 rounded-lg bg-amber-50 px-2 py-1 text-[11px] font-bold text-amber-700">
                ★ {formatRating(business.rating_avg)}
                <span className="mr-1 font-normal text-amber-500">
                  ({fa(business.rating_count)})
                </span>
              </span>
            )}
          </div>

          <p className="mt-0.5 text-[11px] text-slate-400">
            {business.category?.name ?? "دسته‌بندی نشده"}
            {business.subcategory ? ` · ${business.subcategory.name}` : ""}
          </p>

          <p className="mt-1 line-clamp-1 text-xs text-slate-500">{business.short_description}</p>

          <div className="mt-2 flex flex-wrap gap-1.5">
            {business.is_verified && <Badge tone="brand">تأیید شده</Badge>}
            {business.is_24h && <Badge tone="amber">۲۴ ساعته</Badge>}
            {business.distance_m !== null && (
              <Badge tone="slate">{formatDistance(business.distance_m)}</Badge>
            )}
          </div>

          <p className="mt-2 line-clamp-1 text-[11px] text-slate-400">{business.address}</p>
        </div>
      </div>
    </Link>
  );
}
