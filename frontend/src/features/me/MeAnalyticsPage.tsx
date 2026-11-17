import { useState } from "react";

import { Spinner } from "@/components/ui/button";
import { ChartCard, LineChart, type ChartSeries } from "@/features/admin/analytics/charts";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fa, formatRating } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";

interface DailyPoint {
  date: string;
  likes: number;
  quotes: number;
}

interface Analytics {
  business_count: number;
  view_count: number;
  like_count: number;
  rating_avg: number;
  rating_count: number;
  quote_requests: number;
  quote_responded: number;
  series: DailyPoint[];
}

const SERIES: ChartSeries[] = [
  { key: "likes", label: "لایک", color: "#12b886" },
  { key: "quotes", label: "استعلام", color: "#60a5fa" },
];

const RANGES = [7, 30] as const;

export default function MeAnalyticsPage() {
  const analytics = useApi<Analytics>(["me", "analytics"], "/me/analytics");
  const [range, setRange] = useState<(typeof RANGES)[number]>(30);
  const data = analytics.data;

  const points = (data?.series ?? []).slice(-range).map((point) => ({
    label: formatJalali(point.date, { day: "numeric", month: "short" }),
    likes: point.likes,
    quotes: point.quotes,
  }));
  const activity = points.reduce((sum, point) => sum + point.likes + point.quotes, 0);

  return (
    <section className="space-y-4">
      <h1 className="text-lg font-black text-slate-900">آمار کسب‌وکار</h1>

      {analytics.isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {analytics.error && <p className="text-sm text-rose-600">{errorMessage(analytics.error)}</p>}

      {data && data.business_count === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          برای مشاهده آمار ابتدا کسب‌وکار ثبت کنید.
        </p>
      )}

      {data && data.business_count > 0 && (
        <>
          <div className="grid grid-cols-2 gap-3">
            <MetricCard label="بازدید پروفایل" value={fa(data.view_count)} />
            <MetricCard label="لایک‌ها" value={fa(data.like_count)} />
            <MetricCard
              label="میانگین امتیاز"
              value={data.rating_count ? formatRating(data.rating_avg) : "—"}
              hint={`از ${fa(data.rating_count)} نظر`}
            />
            <MetricCard
              label="استعلام‌های دریافتی"
              value={fa(data.quote_requests)}
              hint={`${fa(data.quote_responded)} پاسخ داده‌شده`}
            />
          </div>

          <ChartCard
            title="روند فعالیت"
            description={`لایک‌ها و استعلام‌ها در ${fa(range)} روز گذشته`}
            action={
              <div className="flex rounded-full bg-slate-100 p-0.5">
                {RANGES.map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setRange(option)}
                    className={cn(
                      "rounded-full px-3 py-1 text-[11px] font-bold transition",
                      range === option ? "bg-white text-slate-900 shadow-sm" : "text-slate-500",
                    )}
                  >
                    {fa(option)} روز
                  </button>
                ))}
              </div>
            }
          >
            {activity === 0 ? (
              <p className="py-10 text-center text-xs text-slate-400">
                در این بازه فعالیتی ثبت نشده است.
              </p>
            ) : (
              <LineChart data={points} series={SERIES} height={200} />
            )}
          </ChartCard>
        </>
      )}
    </section>
  );
}

function MetricCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-4">
      <p className="text-[11px] text-slate-500">{label}</p>
      <p className="mt-1 text-2xl font-black text-slate-900">{value}</p>
      {hint && <p className="mt-0.5 text-[10px] text-slate-400">{hint}</p>}
    </div>
  );
}
