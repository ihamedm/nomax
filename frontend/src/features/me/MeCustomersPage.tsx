import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Spinner } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";

interface IncomingQuote {
  id: string;
  title: string;
  description?: string | null;
  status: string;
  is_urgent: boolean;
  address?: string | null;
  neighborhood?: string | null;
  created_at?: string | null;
}

export default function MeCustomersPage() {
  const { data, error, isLoading } = useApi<{ items: IncomingQuote[] }>(
    ["quotes", "incoming"],
    "/quotes/requests/incoming",
  );

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-lg font-black text-slate-900">مشتریان</h1>
        <p className="mt-1 text-xs text-slate-500">
          درخواست‌های قیمت دریافتی از مشتریان در دسته کسب‌وکار شما.
        </p>
      </header>

      {isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}
      {!isLoading && !error && data?.items.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-sm font-bold text-slate-900">درخواستی دریافت نشده است</p>
          <p className="mt-1 text-xs leading-6 text-slate-500">
            درخواست‌های مشتریان هم‌دسته با کسب‌وکار شما اینجا نمایش داده می‌شوند.
          </p>
          <Link to="/me/businesses" className="mt-4 inline-block text-sm text-brand-600">
            مشاهده کسب‌وکارهای من
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
                  {quote.description || "بدون توضیحات"}
                </p>
              </div>
              <Badge tone={quote.is_urgent ? "amber" : "brand"}>
                {quote.is_urgent ? "فوری" : "فعال"}
              </Badge>
            </div>
            <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
              <span>{quote.neighborhood || quote.address || "بدون موقعیت"}</span>
              {quote.created_at && <span>· {formatJalali(quote.created_at)}</span>}
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
