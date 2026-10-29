import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";

interface Quote {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  is_urgent: boolean;
  address?: string | null;
  neighborhood?: string | null;
  created_at?: string | null;
}

const STATUS_LABELS: Record<string, string> = {
  active: "فعال",
  accepted: "پذیرفته‌شده",
  cancelled: "لغوشده",
  expired: "منقضی",
};

function statusTone(status: string): "brand" | "sky" | "amber" | "rose" | "slate" {
  if (status === "active") return "brand";
  if (status === "accepted") return "sky";
  if (status === "expired") return "amber";
  if (status === "cancelled") return "rose";
  return "slate";
}

export default function MeQuotesPage() {
  const { data, error, isLoading } = useApi<{ items: Quote[] }>(
    ["quotes", "mine"],
    "/quotes/requests/mine",
  );

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">درخواست‌های من</h1>
          <p className="mt-1 text-xs text-slate-500">درخواست‌های قیمتی که ثبت کرده‌اید.</p>
        </div>
        <Link to="/quote/new" className="text-sm text-brand-600">
          درخواست جدید
        </Link>
      </header>

      {isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}
      {!isLoading && !error && data?.items.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-sm font-bold text-slate-900">هنوز درخواستی ثبت نکرده‌اید</p>
          <p className="mt-1 text-xs leading-6 text-slate-500">
            برای دریافت پیشنهاد قیمت از کسب‌وکارها، یک درخواست جدید ثبت کنید.
          </p>
          <Link
            to="/quote/new"
            className="mt-4 inline-flex h-10 items-center rounded-xl bg-brand-600 px-4 text-sm font-medium text-white"
          >
            ثبت درخواست
          </Link>
        </div>
      )}

      <div className="space-y-2">
        {data?.items.map((quote) => (
          <article
            key={quote.id}
            className="rounded-2xl border border-slate-200 bg-white p-4"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-slate-900">{quote.title}</p>
                <p className="mt-1 line-clamp-2 text-xs leading-6 text-slate-500">
                  {quote.description || quote.address || "بدون توضیحات"}
                </p>
              </div>
              <Badge tone={statusTone(quote.status)}>
                {STATUS_LABELS[quote.status] ?? quote.status}
              </Badge>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
              {quote.is_urgent && <Badge tone="amber">فوری</Badge>}
              {quote.created_at && <span>{formatJalali(quote.created_at)}</span>}
              {quote.neighborhood && <span>· {quote.neighborhood}</span>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
