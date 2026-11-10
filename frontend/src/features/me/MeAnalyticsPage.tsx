import { useState } from "react";

import { Spinner } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { fa, formatRating } from "@/lib/format";
import { useApi } from "@/lib/query";
import type { BusinessListItem } from "@/types";

interface Analytics {
  business_id: string;
  rating_avg: number;
  rating_count: number;
  approved_reviews: number;
  is_verified: boolean;
}

export default function MeAnalyticsPage() {
  const businesses = useApi<{ items: BusinessListItem[] }>(["me", "businesses"], "/me/businesses");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const activeId = selectedId ?? businesses.data?.items[0]?.id ?? null;

  const analytics = useApi<Analytics>(
    ["me", "analytics", activeId],
    `/me/businesses/${activeId}/analytics`,
    { enabled: Boolean(activeId) },
  );

  return (
    <section className="space-y-4">
      <h1 className="text-lg font-black text-slate-900">آمار کسب‌وکار</h1>

      {businesses.isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {businesses.error && (
        <p className="text-sm text-rose-600">{errorMessage(businesses.error)}</p>
      )}
      {!businesses.isLoading && businesses.data?.items.length === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          برای مشاهده آمار ابتدا کسب‌وکار ثبت کنید.
        </p>
      )}

      {businesses.data && businesses.data.items.length > 0 && (
        <select
          value={activeId ?? ""}
          onChange={(event) => setSelectedId(event.target.value)}
          className="w-full rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm"
        >
          {businesses.data.items.map((business) => (
            <option key={business.id} value={business.id}>
              {business.name}
            </option>
          ))}
        </select>
      )}

      {analytics.isLoading && (
        <div className="flex justify-center py-10 text-brand-600">
          <Spinner />
        </div>
      )}
      {analytics.error && <p className="text-sm text-rose-600">{errorMessage(analytics.error)}</p>}
      {analytics.data && (
        <div className="grid grid-cols-2 gap-3">
          {[
            { label: "میانگین امتیاز", value: formatRating(analytics.data.rating_avg) },
            { label: "تعداد امتیاز", value: fa(analytics.data.rating_count) },
            { label: "نظرات تأییدشده", value: fa(analytics.data.approved_reviews) },
            { label: "وضعیت مجوز", value: analytics.data.is_verified ? "تأییدشده" : "تأییدنشده" },
          ].map((card) => (
            <div key={card.label} className="rounded-2xl border border-slate-200 bg-white p-4">
              <p className="text-xs text-slate-500">{card.label}</p>
              <p className="mt-1 text-lg font-bold text-slate-900">{card.value}</p>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
