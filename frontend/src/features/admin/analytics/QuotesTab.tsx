import { Badge } from "@/components/ui/badge";
import { toFa } from "@/lib/digits";
import type { QuoteAnalytics } from "./types";
import { ChartCard, DonutChart, TimingBars } from "./charts";
import {
  QUOTE_STATUS_COLORS,
  QUOTE_STATUS_LABELS,
  TIMING_LABELS,
  formatDuration,
  formatNumber,
} from "./analytics-utils";

function QuoteWidget({
  label,
  value,
  hint,
  icon,
  tone = "text-slate-900",
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: string;
  tone?: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-3.5">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] text-slate-400">{label}</p>
        <span className="text-base" aria-hidden>
          {icon}
        </span>
      </div>
      <p className={`mt-1 text-xl font-black ${tone}`}>{value}</p>
      {hint && <p className="mt-1 text-[10px] text-slate-400">{hint}</p>}
    </div>
  );
}

export function QuotesTab({ data }: { data: QuoteAnalytics }) {
  const statusItems = data.statuses.map((item) => ({
    label: QUOTE_STATUS_LABELS[item.status] ?? item.status,
    value: item.count,
    color: QUOTE_STATUS_COLORS[item.status] ?? "#94a3b8",
  }));
  const timingItems = data.timings.map((item, index) => ({
    label: TIMING_LABELS[item.key] ?? item.key,
    seconds: item.avg_seconds,
    count: item.count,
    color: ["#0f172a", "#0284c7", "#10a56f", "#d97706"][index] ?? "#64748b",
  }));
  const w = data.widgets;

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-6">
        <QuoteWidget
          label="کل استعلام‌ها"
          value={formatNumber(w.total)}
          hint={`${toFa(w.active)} فعال`}
          icon="⌕"
          tone="text-slate-900"
        />
        <QuoteWidget
          label="پذیرفته‌شده"
          value={formatNumber(w.accepted)}
          hint={`${toFa(w.choice_rate)}٪ نرخ انتخاب`}
          icon="✓"
          tone="text-brand-700"
        />
        <QuoteWidget
          label="پیشنهادها"
          value={formatNumber(w.offers_total)}
          hint={`${toFa(w.pending_offers)} در انتظار`}
          icon="✉"
          tone="text-sky-700"
        />
        <QuoteWidget
          label="نرخ پاسخ مالکان"
          value={`${toFa(w.response_rate)}٪`}
          hint={`${toFa(w.responded_requests)} استعلام پاسخ داده‌شده`}
          icon="💬"
          tone="text-amber-700"
        />
        <QuoteWidget
          label="میانگین اولین پیشنهاد"
          value={formatDuration(w.avg_offer_seconds)}
          hint="از ثبت درخواست"
          icon="⏱"
          tone="text-slate-900"
        />
        <QuoteWidget
          label="میانگین انتخاب مشتری"
          value={formatDuration(w.avg_choice_seconds)}
          hint={`${toFa(w.chosen_quotes)} استعلام موفق`}
          icon="🏁"
          tone="text-brand-700"
        />
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <ChartCard
          title="استعلام‌ها بر اساس وضعیت"
          description="توزیع همه درخواست‌های قیمت در چهار وضعیت"
        >
          <DonutChart
            items={statusItems}
            centerValue={formatNumber(w.total)}
            centerLabel="کل استعلام"
          />
        </ChartCard>

        <ChartCard
          title="زمان‌های کلیدی قیف استعلام"
          description="میانگین فاصله زمانی از ثبت درخواست تا هر مرحله"
        >
          <TimingBars items={timingItems} />
        </ChartCard>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <ChartCard
          title="بازخورد بازار"
          description="چه مقدار از درخواست‌ها به مالکان رسیده و دیده شده‌اند؟"
        >
          <div className="space-y-3">
            {[
              {
                label: "درخواست‌های دیده‌شده",
                value: w.seen_requests,
                rate: w.seen_rate,
                color: "#0284c7",
              },
              {
                label: "درخواست‌های پاسخ‌داده‌شده",
                value: w.responded_requests,
                rate: w.response_rate,
                color: "#10a56f",
              },
              {
                label: "درخواست‌های انتخاب‌شده",
                value: w.chosen_quotes,
                rate: w.choice_rate,
                color: "#d97706",
              },
            ].map((item) => (
              <div key={item.label}>
                <div className="flex items-center justify-between text-[11px]">
                  <span className="text-slate-600">{item.label}</span>
                  <span className="font-bold text-slate-800">
                    {toFa(item.value)} · {toFa(item.rate)}٪
                  </span>
                </div>
                <div className="mt-1.5 h-2 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full"
                    style={{ width: `${Math.min(100, item.rate)}%`, backgroundColor: item.color }}
                  />
                </div>
              </div>
            ))}
          </div>
        </ChartCard>

        <ChartCard
          title="جزئیات پیشنهادها"
          description="وضعیت پیشنهادهای ثبت‌شده توسط کسب‌وکارها"
        >
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "کل پیشنهادها", value: w.offers_total },
              { label: "پیشنهاد پذیرفته‌شده", value: w.accepted_offers },
              { label: "در انتظار پاسخ", value: w.pending_offers },
              { label: "مالکان پاسخ‌داده", value: w.responded_requests },
            ].map((item) => (
              <div key={item.label} className="rounded-xl bg-slate-50 p-3">
                <p className="text-[10px] text-slate-400">{item.label}</p>
                <p className="mt-1 text-lg font-black text-slate-800">{toFa(item.value)}</p>
              </div>
            ))}
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            <Badge tone="slate">مبنای زمان: ثبت درخواست</Badge>
            <Badge tone="amber">پیشنهاد ردشده در زمان‌ها حساب نمی‌شود</Badge>
          </div>
        </ChartCard>
      </div>
    </div>
  );
}
