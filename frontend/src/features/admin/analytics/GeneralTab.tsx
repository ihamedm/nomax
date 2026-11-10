import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { toFa } from "@/lib/digits";
import type { AnalyticsOverview } from "./types";
import {
  BarChart,
  ChartCard,
  DonutChart,
  HorizontalBars,
  LineChart,
  type ChartSeries,
} from "./charts";
import {
  FUNNEL_LABELS,
  formatNumber,
  roleEmoji,
  shortDateLabel,
} from "./analytics-utils";

const ROLE_COLORS: Record<string, string> = {
  customer: "#10a56f",
  owner: "#0284c7",
  admin: "#d97706",
  superadmin: "#7c3aed",
};

const FUNNEL_SERIES: ChartSeries[] = [
  { key: "requests", label: "درخواست", color: "#0f172a" },
  { key: "sent", label: "ارسال به کسب‌وکار", color: "#64748b" },
  { key: "seen", label: "مشاهده‌شده", color: "#0284c7" },
  { key: "responded", label: "پاسخ/پیشنهاد", color: "#10a56f" },
  { key: "chosen", label: "انتخاب مشتری", color: "#d97706" },
];

const DAILY_SERIES: ChartSeries[] = [
  { key: "searches", label: "جستجو", color: "#10a56f" },
  { key: "quote_requests", label: "درخواست قیمت", color: "#0284c7" },
  { key: "quote_responses", label: "پاسخ به استعلام", color: "#d97706" },
  { key: "registrations", label: "ثبت‌نام", color: "#7c3aed" },
];

const HOURLY_SERIES: ChartSeries[] = [
  { key: "searches", label: "جستجو", color: "#10a56f" },
  { key: "quote_requests", label: "درخواست قیمت", color: "#0284c7" },
];

function Widget({
  label,
  value,
  hint,
  icon,
  tone = "text-slate-900",
  href,
}: {
  label: string;
  value: number;
  hint?: string;
  icon: string;
  tone?: string;
  href?: string;
}) {
  const content = (
    <div className="h-full rounded-2xl border border-slate-200 bg-white p-3.5 transition-colors hover:border-brand-300">
      <div className="flex items-start justify-between gap-2">
        <p className="text-[11px] text-slate-400">{label}</p>
        <span className="text-base" aria-hidden>
          {icon}
        </span>
      </div>
      <p className={`mt-1 text-xl font-black ${tone}`}>{formatNumber(value)}</p>
      {hint && <p className="mt-1 text-[10px] text-slate-400">{hint}</p>}
    </div>
  );
  return href ? (
    <Link to={href} className="block h-full">
      {content}
    </Link>
  ) : (
    content
  );
}

export function GeneralTab({ data }: { data: AnalyticsOverview }) {
  const daily = data.daily.map((point) => ({
    ...point,
    label: shortDateLabel(point.date),
  }));
  const hourly = data.hourly.map((point) => ({
    label: toFa(point.hour),
    values: {
      searches: point.searches,
      quote_requests: point.quote_requests,
    },
  }));
  const funnel = data.quote_funnel.map((item) => ({
    label: FUNNEL_LABELS[item.range] ?? item.range,
    values: item.counts as unknown as Record<string, number>,
  }));
  const roles = data.roles.map((item) => ({
    label: `${roleEmoji(item.role)} ${item.label}`,
    value: item.count,
    color: ROLE_COLORS[item.role] ?? "#94a3b8",
  }));
  const pendingItems = [
    {
      label: "کسب‌وکار",
      icon: "🏪",
      values: { count: data.pending.businesses },
      total: data.pending.businesses,
    },
    {
      label: "نظرات",
      icon: "★",
      values: { count: data.pending.reviews },
      total: data.pending.reviews,
    },
    {
      label: "استعلام بدون پیشنهاد",
      icon: "⌕",
      values: { count: data.pending.quotes },
      total: data.pending.quotes,
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2 lg:grid-cols-6">
        <Widget
          label="کسب‌وکارها"
          value={data.widgets.businesses_total}
          hint={`${toFa(data.widgets.businesses_approved)} تأییدشده`}
          icon="🏪"
          tone="text-brand-700"
          href="/admin/businesses"
        />
        <Widget
          label="نظرات"
          value={data.widgets.reviews_total}
          hint="کل نظرات ثبت‌شده"
          icon="★"
          href="/admin/reviews"
        />
        <Widget
          label="استعلام‌ها"
          value={data.widgets.quotes_total}
          hint="کل درخواست‌های قیمت"
          icon="⌕"
          href="/admin/quotes"
        />
        <Widget
          label="جستجوها"
          value={data.widgets.searches_total}
          hint="کل جستجوهای ثبت‌شده"
          icon="🔎"
        />
        <Widget
          label="کاربران"
          value={data.widgets.users_total}
          hint="همه نقش‌ها"
          icon="👥"
          href="/admin/users"
        />
        <Link
          to="/admin/businesses?status=pending"
          className="h-full rounded-2xl border border-amber-200 bg-amber-50 p-3.5 transition-colors hover:border-amber-300"
        >
          <div className="flex items-start justify-between gap-2">
            <p className="text-[11px] text-amber-700">نیازمند اقدام</p>
            <span className="text-base" aria-hidden>
              🔔
            </span>
          </div>
          <p className="mt-1 text-xl font-black text-amber-700">{toFa(data.pending.total)}</p>
          <p className="mt-1 text-[10px] text-amber-700/70">
            {toFa(data.pending.businesses)} کسب‌وکار · {toFa(data.pending.reviews)} نظر ·{" "}
            {toFa(data.pending.quotes)} استعلام
          </p>
        </Link>
      </div>

      <div className="grid gap-3 xl:grid-cols-3">
        <ChartCard
          title="روند فعالیت"
          description="جستجو، درخواست قیمت، پاسخ مالکان و ثبت‌نام در ۱۴ روز اخیر"
          className="xl:col-span-2"
        >
          <LineChart data={daily} series={DAILY_SERIES} height={250} />
        </ChartCard>

        <ChartCard
          title="ترکیب کاربران"
          description="تعداد کاربران بر اساس نقش"
        >
          <DonutChart
            items={roles}
            centerValue={formatNumber(data.widgets.users_total)}
            centerLabel="کاربر"
          />
        </ChartCard>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <ChartCard
          title="قیف استعلام قیمت"
          description="از ثبت درخواست تا انتخاب پیشنهاد، در بازه‌های مختلف"
        >
          <BarChart items={funnel} series={FUNNEL_SERIES} height={190} showValues />
        </ChartCard>

        <ChartCard
          title="فعالیت امروز به تفکیک ساعت"
          description="جستجو و درخواست قیمت در ۲۴ ساعت امروز"
        >
          <BarChart items={hourly} series={HOURLY_SERIES} height={190} labelEvery={3} />
        </ChartCard>
      </div>

      <div className="grid gap-3 xl:grid-cols-2">
        <ChartCard
          title="کارهای نیازمند اقدام"
          description="مواردی که منتظر بررسی یا واکنش هستند"
        >
          <HorizontalBars
            items={pendingItems}
            series={[{ key: "count", label: "تعداد", color: "#d97706" }]}
            labelWidth={130}
          />
          <div className="mt-4 flex flex-wrap gap-2">
            <Link
              to="/admin/businesses?status=pending"
              className="rounded-full border border-slate-200 px-3 py-1.5 text-[10px] text-slate-600 hover:border-amber-300"
            >
              بررسی کسب‌وکارهای در انتظار
            </Link>
            <Link
              to="/admin/reviews?status=pending"
              className="rounded-full border border-slate-200 px-3 py-1.5 text-[10px] text-slate-600 hover:border-amber-300"
            >
              بررسی نظرات در انتظار
            </Link>
            <Link
              to="/admin/quotes"
              className="rounded-full border border-slate-200 px-3 py-1.5 text-[10px] text-slate-600 hover:border-amber-300"
            >
              استعلام‌های بدون پیشنهاد
            </Link>
          </div>
        </ChartCard>

        <ChartCard
          title="سلامت بازار"
          description="نسبت تقاضا به عرضه در دسته‌های اصلی"
        >
          <div className="grid grid-cols-2 gap-2">
            {[
              { label: "جستجوی امروز", value: data.hourly.reduce((sum, item) => sum + item.searches, 0) },
              {
                label: "استعلام امروز",
                value: data.hourly.reduce((sum, item) => sum + item.quote_requests, 0),
              },
              {
                label: "استعلام‌های منتظر",
                value: data.pending.quotes,
              },
              {
                label: "میانگین جستجوی روزانه",
                value: Math.round(
                  data.daily.reduce((sum, item) => sum + item.searches, 0) /
                    Math.max(data.daily.length, 1),
                ),
              },
            ].map((item) => (
              <div key={item.label} className="rounded-xl bg-slate-50 p-3">
                <p className="text-[10px] text-slate-400">{item.label}</p>
                <p className="mt-1 text-lg font-black text-slate-800">{formatNumber(item.value)}</p>
              </div>
            ))}
          </div>
          <div className="mt-3 flex items-center justify-between rounded-xl border border-dashed border-slate-200 px-3 py-2">
            <span className="text-[10px] text-slate-500">برای تحلیل کامل عرضه و تقاضا</span>
            <Link to="/admin/analytics?tab=market" className="text-[10px] font-bold text-brand-600">
              بازار و تقاضا ←
            </Link>
          </div>
        </ChartCard>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <Badge tone="slate">تحلیل‌ها بر اساس زمان تهران</Badge>
        <Badge tone="brand">جستجوهای صفحه اول</Badge>
      </div>
    </div>
  );
}
