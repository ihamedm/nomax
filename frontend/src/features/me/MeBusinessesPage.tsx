import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { useApi } from "@/lib/query";
import { formatRating } from "@/lib/format";
import type { BusinessListItem } from "@/types";

const STATUS_META: Record<
  string,
  { label: string; tone: "brand" | "amber" | "rose" | "slate" }
> = {
  approved: { label: "تأییدشده", tone: "brand" },
  pending: { label: "در انتظار تأیید", tone: "amber" },
  rejected: { label: "ردشده", tone: "rose" },
};

export default function MeBusinessesPage() {
  const { data, error, isLoading } = useApi<{
    items: BusinessListItem[];
    limit: number;
    can_create: boolean;
  }>(["me", "businesses"], "/me/businesses");
  const canCreate = data?.can_create ?? true;

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">کسب‌وکارهای من</h1>
          <p className="mt-1 text-xs text-slate-500">فقط کسب‌وکارهایی که مالک آن‌ها هستید.</p>
        </div>
        {canCreate && (
          <Link to="/businesses/new" className="text-sm text-brand-600">
            ثبت جدید
          </Link>
        )}
      </header>

      {data && !canCreate && (
        <p className="rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-[11px] leading-5 text-amber-800">
          شما به سقف مجاز ثبت کسب‌وکار ({data.limit.toLocaleString("fa-IR")}) رسیده‌اید.
        </p>
      )}

      {isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}
      {!isLoading && !error && data?.items.length === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          هنوز کسب‌وکاری ثبت نکرده‌اید.
        </p>
      )}

      {data?.items.map((business) => {
        const status = business.status ?? (business.is_verified ? "approved" : "pending");
        const meta = STATUS_META[status] ?? STATUS_META.pending;
        return (
          <article
            key={business.id}
            className={
              status === "rejected"
                ? "rounded-2xl border border-rose-200 bg-white p-4"
                : "rounded-2xl border border-slate-200 bg-white p-4"
            }
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-slate-900">{business.name}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {business.category?.name ?? "بدون دسته"} · {business.address}
                </p>
              </div>
              <Badge tone={meta.tone}>{meta.label}</Badge>
            </div>
            {status === "rejected" && business.rejection_reason && (
              <p className="mt-3 rounded-xl bg-rose-50 px-3 py-2 text-[11px] leading-5 text-rose-700">
                دلیل رد: {business.rejection_reason}
              </p>
            )}
            {status === "pending" && (
              <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800">
                این کسب‌وکار در صف بررسی مدیر است. با ویرایش، اطلاعات به‌روز شده و دوباره
                ارسال می‌شود.
              </p>
            )}
            <div className="mt-3 flex items-center justify-between text-xs text-slate-500">
              <span>
                ⭐ {formatRating(business.rating_avg)} ({business.rating_count} نظر)
              </span>
              <div className="flex items-center gap-3">
                <Link to={`/businesses/${business.id}/edit`} className="text-brand-600">
                  {status === "rejected" ? "اصلاح و ارسال دوباره" : "ویرایش"}
                </Link>
                <Link to={`/businesses/${business.slug}`} className="text-brand-600">
                  مشاهده
                </Link>
              </div>
            </div>
          </article>
        );
      })}
    </section>
  );
}
