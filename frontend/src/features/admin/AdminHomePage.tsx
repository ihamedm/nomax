import { keepPreviousData } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import { fa, formatPhone, permissionLabel, ROLE_LABELS } from "@/lib/format";
import { formatRelative } from "@/lib/jalali";
import { useApi } from "@/lib/query";
import { useAuth } from "@/stores/auth";

import {
  ChartCard,
  DonutChart,
  HorizontalBars,
  LineChart,
  type ChartSeries,
} from "./analytics/charts";
import { formatNumber, roleEmoji, shortDateLabel } from "./analytics/analytics-utils";

/* ------------------------------------------------------------------ types */

interface StatBucket {
  total: number;
  last_7d: number;
  change: number | null;
}

interface DashboardStats {
  businesses: StatBucket & { approved: number; pending: number; rejected: number };
  users: StatBucket & { verified: number; verified_rate: number };
  reviews: StatBucket & { pending: number; avg_rating: number };
  quotes: StatBucket & { active: number; unanswered: number };
  searches: StatBucket & { no_result_7d: number; no_result_rate: number };
}

interface TrendPoint {
  date: string;
  users: number;
  businesses: number;
  reviews: number;
  quotes: number;
  searches: number;
}

interface QueueItem {
  key: string;
  label: string;
  count: number;
  to: string;
  tone: "amber" | "rose" | "brand" | string;
}

interface ActivityItem {
  id: string;
  type: string;
  occurred_at: string | null;
  user_name: string;
  title: string;
  detail: string | null;
}

interface DashboardData {
  generated_at: string;
  days: number;
  stats: DashboardStats | null;
  trend?: TrendPoint[];
  business_status?: Array<{ status: string; label: string; color: string; count: number }>;
  roles?: Array<{ role: string; label: string; count: number }>;
  top_categories?: Array<{ id: number; name: string; icon: string; businesses: number; searches: number }>;
  queues: QueueItem[];
  recent_activity: ActivityItem[];
}

interface Shortcut {
  to: string;
  title: string;
  icon: string;
  permission: string | null;
  superadminOnly?: boolean;
}

/* -------------------------------------------------------------- constants */

const TREND_SERIES: ChartSeries[] = [
  { key: "users", label: "کاربر جدید", color: "#6366f1" },
  { key: "businesses", label: "کسب‌وکار", color: "#10b981" },
  { key: "quotes", label: "استعلام", color: "#f59e0b" },
  { key: "searches", label: "جستجو", color: "#0ea5e9" },
];

const ROLE_COLORS: Record<string, string> = {
  customer: "#10a56f",
  owner: "#0284c7",
  admin: "#f59e0b",
  superadmin: "#8b5cf6",
};

const QUEUE_TONES: Record<string, { ring: string; chip: string; text: string }> = {
  amber: { ring: "hover:border-amber-300", chip: "bg-amber-100 text-amber-700", text: "text-amber-600" },
  rose: { ring: "hover:border-rose-300", chip: "bg-rose-100 text-rose-700", text: "text-rose-600" },
  brand: { ring: "hover:border-brand-300", chip: "bg-brand-50 text-brand-700", text: "text-brand-600" },
};

const ACTIVITY_ICONS: Record<string, string> = {
  search: "🔍",
  user_registered: "👤",
  business_created: "🏪",
  review_created: "⭐",
  quote_requested: "📋",
  quote_offer: "💬",
  quote_seen: "👀",
  quote_chosen: "🤝",
};

const SHORTCUTS: Shortcut[] = [
  { to: "/admin/businesses", title: "کسب‌وکارها", icon: "🏪", permission: "business.read" },
  { to: "/admin/reviews", title: "نظرات", icon: "⭐", permission: "review.read" },
  { to: "/admin/quotes", title: "استعلام‌ها", icon: "📋", permission: "quote.read" },
  { to: "/admin/categories", title: "دسته‌بندی‌ها", icon: "🗂", permission: "category.read" },
  { to: "/admin/tags", title: "برچسب‌ها", icon: "🏷", permission: "category.read" },
  { to: "/admin/ads", title: "بنرها", icon: "🖼", permission: "ad.manage" },
  { to: "/admin/analytics", title: "تحلیل بازار", icon: "📈", permission: "stats.read" },
  { to: "/admin/notifications", title: "اعلان‌ها", icon: "🔔", permission: "notification.manage" },
  { to: "/admin/settings", title: "تنظیمات", icon: "⚙️", permission: "admin.settings.manage" },
  { to: "/admin/cache", title: "کش‌ها", icon: "⚡", permission: "admin.settings.manage" },
  { to: "/admin/files", title: "فایل‌ها", icon: "📦", permission: "storage.manage" },
  { to: "/admin/users", title: "کاربران", icon: "👥", permission: null, superadminOnly: true },
  { to: "/admin/backups", title: "پشتیبان", icon: "💾", permission: null, superadminOnly: true },
  { to: "/admin/data", title: "مدل داده", icon: "🗄", permission: null, superadminOnly: true },
];

/* ------------------------------------------------------------- components */

function greeting(): string {
  const hour = new Date().getHours();
  if (hour < 6) return "شب بخیر";
  if (hour < 12) return "صبح بخیر";
  if (hour < 17) return "ظهر بخیر";
  if (hour < 20) return "عصر بخیر";
  return "شب بخیر";
}

/** Persian digits with the Persian decimal separator (٫) instead of ".". */
function faDecimal(value: number): string {
  return fa(String(Math.round(value * 10) / 10)).replace(".", "٫");
}

function Delta({ value }: { value: number | null }) {
  if (value === null) {
    return <span className="text-[10px] text-slate-400">بدون سابقه</span>;
  }
  const zero = Math.abs(value) < 0.05;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-0.5 rounded-full px-1.5 py-0.5 text-[10px] font-bold",
        zero && "bg-slate-100 text-slate-500",
        !zero && value > 0 && "bg-emerald-50 text-emerald-600",
        !zero && value < 0 && "bg-rose-50 text-rose-600",
      )}
    >
      {!zero && <span aria-hidden>{value > 0 ? "▲" : "▼"}</span>}
      {faDecimal(Math.abs(value))}٪
    </span>
  );
}

/** Tiny inline trend line: no axes, no labels, just shape. */
function Sparkline({ values, color }: { values: number[]; color: string }) {
  if (values.length < 2) return null;
  const width = 120;
  const height = 26;
  const max = Math.max(1, ...values);
  const step = width / (values.length - 1);
  const points = values.map((value, index) => {
    const x = index * step;
    const y = height - 3 - (value / max) * (height - 8);
    return `${x.toFixed(1)} ${y.toFixed(1)}`;
  });
  const line = `M${points.join(" L")}`;
  return (
    <svg
      viewBox={`0 0 ${width} ${height}`}
      preserveAspectRatio="none"
      className="mt-2 h-6 w-full"
      aria-hidden
    >
      <path d={`${line} L${width} ${height} L0 ${height} Z`} fill={color} opacity="0.1" />
      <path
        d={line}
        fill="none"
        stroke={color}
        strokeWidth="1.6"
        strokeLinejoin="round"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

function StatCard({
  icon,
  label,
  value,
  stats,
  change,
  accent,
  sparkline,
  sparkColor,
}: {
  icon: string;
  label: string;
  value: number;
  stats: Array<{ label: string; value: string; tone?: string }>;
  change: number | null;
  accent: string;
  sparkline?: number[];
  sparkColor?: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-3.5 transition-shadow hover:shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <span className="flex min-w-0 items-center gap-1.5 text-[11px] font-medium text-slate-500">
          <span className={cn("grid h-6 w-6 shrink-0 place-items-center rounded-lg text-xs", accent)}>
            {icon}
          </span>
          <span className="truncate">{label}</span>
        </span>
        <Delta value={change} />
      </div>
      <p className="mt-2 text-[26px] font-black leading-none tracking-tight text-slate-900">{formatNumber(value)}</p>
      <div className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[10px] text-slate-400">
        {stats.map((item) => (
          <span key={item.label} className="whitespace-nowrap">
            {item.label}{" "}
            <span className={cn("font-bold", item.tone ?? "text-slate-600")}>{item.value}</span>
          </span>
        ))}
      </div>
      {sparkline && sparkColor && <Sparkline values={sparkline} color={sparkColor} />}
    </div>
  );
}

function QueueTile({ item }: { item: QueueItem }) {
  const tone = QUEUE_TONES[item.tone] ?? QUEUE_TONES.brand;
  const empty = item.count === 0;
  return (
    <Link
      to={item.to}
      className={cn(
        "flex items-center gap-3 rounded-2xl border bg-white p-3 transition-colors",
        empty ? "border-slate-200" : "border-slate-200",
        tone.ring,
      )}
    >
      <span
        className={cn(
          "grid h-10 w-10 shrink-0 place-items-center rounded-xl text-sm font-black",
          empty ? "bg-slate-100 text-slate-400" : tone.chip,
        )}
      >
        {formatNumber(item.count)}
      </span>
      <span className="min-w-0 flex-1">
        <span className="block truncate text-xs font-medium text-slate-700">{item.label}</span>
        <span className={cn("mt-0.5 block text-[10px]", empty ? "text-slate-400" : tone.text)}>
          {empty ? "صف خالی است" : "نیازمند بررسی"}
        </span>
      </span>
      <span className="text-[10px] text-slate-300">←</span>
    </Link>
  );
}

function ActivityFeed({ items }: { items: ActivityItem[] }) {
  return (
    <ChartCard
      title="آخرین رویدادها"
      description="جدیدترین فعالیت کاربران و کسب‌وکارها"
      className="self-start"
    >
      {items.length === 0 ? (
        <p className="py-8 text-center text-[11px] text-slate-400">هنوز رویدادی ثبت نشده است.</p>
      ) : (
        <ol className="space-y-3">
          {items.map((item) => (
            <li key={item.id} className="flex items-start gap-2.5">
              <span className="grid h-7 w-7 shrink-0 place-items-center rounded-full bg-slate-50 text-xs">
                {ACTIVITY_ICONS[item.type] ?? "•"}
              </span>
              <div className="min-w-0 flex-1 border-b border-dashed border-slate-100 pb-2.5 last:border-0">
                <p className="truncate text-[11px] font-medium text-slate-700">{item.title}</p>
                <p className="mt-0.5 flex items-center gap-1.5 text-[10px] text-slate-400">
                  <span className="truncate">{item.user_name}</span>
                  <span aria-hidden>•</span>
                  <span className="shrink-0">
                    {item.occurred_at ? formatRelative(item.occurred_at) : "—"}
                  </span>
                </p>
              </div>
            </li>
          ))}
        </ol>
      )}
    </ChartCard>
  );
}

/* -------------------------------------------------------------------- page */

export function AdminHomePage() {
  const user = useAuth((state) => state.user);
  const [days, setDays] = useState(14);
  const dashboard = useApi<DashboardData>(["admin", "dashboard", days], `/admin/dashboard?days=${days}`, {
    enabled: Boolean(user),
    staleTime: 60_000,
    placeholderData: keepPreviousData,
  });

  if (!user) return null;

  const data = dashboard.data;
  const stats = data?.stats ?? null;
  const loading = dashboard.isPending;
  const isSuper = user.role === "superadmin";

  const shortcuts = SHORTCUTS.filter((item) => {
    if (item.superadminOnly && !isSuper) return false;
    if (item.permission && !isSuper && !user.permissions.includes(item.permission)) return false;
    return true;
  });

  const trend = (data?.trend ?? []).map((point) => ({
    label: shortDateLabel(point.date),
    users: point.users,
    businesses: point.businesses,
    reviews: point.reviews,
    quotes: point.quotes,
    searches: point.searches,
  }));
  const spark = {
    businesses: trend.map((point) => point.businesses),
    users: trend.map((point) => point.users),
    reviews: trend.map((point) => point.reviews),
    quotes: trend.map((point) => point.quotes),
    searches: trend.map((point) => point.searches),
  };

  const pendingTotal = (data?.queues ?? []).reduce((sum, item) => sum + item.count, 0);

  return (
    <section className="space-y-3.5">
      {/* hero */}
      <div className="relative overflow-hidden rounded-3xl bg-gradient-to-l from-brand-600 via-brand-500 to-brand-400 p-5 text-white">
        <div
          aria-hidden
          className="pointer-events-none absolute -left-10 -top-16 h-44 w-44 rounded-full bg-white/10 blur-2xl"
        />
        <div
          aria-hidden
          className="pointer-events-none absolute -bottom-20 right-10 h-40 w-40 rounded-full bg-white/10 blur-2xl"
        />
        <div className="relative flex flex-wrap items-start justify-between gap-4">
          <div>
            <p className="text-[11px] text-white/70">{greeting()}</p>
            <h1 className="mt-1 text-[22px] font-black leading-tight">
              {user.full_name || formatPhone(user.phone)}
            </h1>
            <div className="mt-2.5 flex flex-wrap items-center gap-2">
              <span className="rounded-full bg-white/15 px-2.5 py-1 text-[10px]">
                {ROLE_LABELS[user.role]}
              </span>
              {isSuper ? (
                <span className="rounded-full bg-white/15 px-2.5 py-1 text-[10px]">
                  دسترسی کامل
                </span>
              ) : (
                <span className="rounded-full bg-white/15 px-2.5 py-1 text-[10px]">
                  {user.permissions.length === 0
                    ? "بدون دسترسی واگذارشده"
                    : `${fa(user.permissions.length)} دسترسی`}
                </span>
              )}
              {data && (
                <span className="text-[10px] text-white/60">
                  به‌روزرسانی {formatRelative(data.generated_at)}
                </span>
              )}
            </div>
          </div>

          <div className="flex flex-col items-end gap-2">
            <div className="rounded-2xl bg-white/10 px-4 py-2 text-right backdrop-blur">
              <p className="text-[10px] text-white/70">کارهای در انتظار</p>
              <p className="text-[19px] font-black leading-tight">{formatNumber(pendingTotal)}</p>
            </div>
            {(isSuper || user.permissions.includes("stats.read")) && (
              <Link
                to="/admin/analytics"
                className="rounded-full bg-white px-3 py-1.5 text-[10px] font-bold text-brand-700 hover:bg-white/90"
              >
                گزارش کامل ←
              </Link>
            )}
          </div>
        </div>
      </div>

      {/* first load skeleton */}
      {loading && !data && (
        <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-3 xl:grid-cols-5">
          {Array.from({ length: 5 }).map((_, index) => (
            <div
              key={index}
              className="h-[92px] animate-pulse rounded-2xl border border-slate-200 bg-white"
            />
          ))}
        </div>
      )}

      {/* KPI row */}
      {stats && (
        <div className="grid grid-cols-2 gap-2.5 lg:grid-cols-3 xl:grid-cols-5">
          <StatCard
            icon="🏪"
            label="کسب‌وکارها"
            value={stats.businesses.total}
            stats={[
              { label: "تأییدشده", value: formatNumber(stats.businesses.approved), tone: "text-emerald-600" },
              { label: "در انتظار", value: formatNumber(stats.businesses.pending), tone: "text-amber-600" },
            ]}
            change={stats.businesses.change}
            accent="bg-emerald-50 text-emerald-600"
            sparkline={spark.businesses}
            sparkColor="#10b981"
          />
          <StatCard
            icon="👥"
            label="کاربران"
            value={stats.users.total}
            stats={[
              { label: "تأییدشده", value: formatNumber(stats.users.verified), tone: "text-indigo-600" },
              { label: "هفته اخیر", value: formatNumber(stats.users.last_7d), tone: "text-slate-600" },
            ]}
            change={stats.users.change}
            accent="bg-brand-50 text-brand-700"
            sparkline={spark.users}
            sparkColor="#6366f1"
          />
          <StatCard
            icon="⭐"
            label="نظرات"
            value={stats.reviews.total}
            stats={[
              { label: "میانگین", value: faDecimal(stats.reviews.avg_rating), tone: "text-amber-600" },
              { label: "در انتظار", value: formatNumber(stats.reviews.pending), tone: "text-rose-600" },
            ]}
            change={stats.reviews.change}
            accent="bg-amber-50 text-amber-600"
            sparkline={spark.reviews}
            sparkColor="#f59e0b"
          />
          <StatCard
            icon="📋"
            label="استعلام‌ها"
            value={stats.quotes.total}
            stats={[
              { label: "فعال", value: formatNumber(stats.quotes.active), tone: "text-sky-600" },
              { label: "بی‌پاسخ", value: formatNumber(stats.quotes.unanswered), tone: "text-rose-600" },
            ]}
            change={stats.quotes.change}
            accent="bg-sky-100 text-sky-700"
            sparkline={spark.quotes}
            sparkColor="#0ea5e9"
          />
          <StatCard
            icon="🔍"
            label="جستجوها"
            value={stats.searches.total}
            stats={[
              { label: "بدون نتیجه", value: `${faDecimal(stats.searches.no_result_rate)}٪`, tone: "text-slate-600" },
              { label: "هفته اخیر", value: formatNumber(stats.searches.last_7d), tone: "text-slate-600" },
            ]}
            change={stats.searches.change}
            accent="bg-slate-100 text-slate-600"
            sparkline={spark.searches}
            sparkColor="#64748b"
          />
        </div>
      )}

      {/* trend + status */}
      {stats && (
        <div className="grid gap-3 xl:grid-cols-3">
          <ChartCard
            title="روند رشد"
            description="فعالیت روزانه پلتفرم در بازه انتخابی"
            className="xl:col-span-2"
            action={
              <div className="flex rounded-full bg-slate-100 p-0.5 text-[10px]">
                {[
                  { value: 7, label: "۷ روز" },
                  { value: 14, label: "۱۴ روز" },
                  { value: 30, label: "۳۰ روز" },
                ].map((option) => (
                  <button
                    key={option.value}
                    type="button"
                    onClick={() => setDays(option.value)}
                    className={cn(
                      "rounded-full px-2.5 py-1 font-medium transition-colors",
                      days === option.value
                        ? "bg-white text-slate-900 shadow-sm"
                        : "text-slate-500 hover:text-slate-700",
                    )}
                  >
                    {option.label}
                  </button>
                ))}
              </div>
            }
          >
            {trend.length > 0 ? (
              <LineChart data={trend} series={TREND_SERIES} height={250} />
            ) : (
              <p className="py-16 text-center text-[11px] text-slate-400">داده‌ای برای نمایش نیست.</p>
            )}
          </ChartCard>

          <ChartCard title="وضعیت کسب‌وکارها" description="توزیع کسب‌وکارهای ثبت‌شده">
            <DonutChart
              items={(data?.business_status ?? []).map((row) => ({
                label: row.label,
                value: row.count,
                color: row.color,
              }))}
              centerValue={formatNumber(stats.businesses.total)}
              centerLabel="کسب‌وکار"
            />
            <dl className="mt-4 grid grid-cols-2 gap-2 border-t border-slate-100 pt-3">
              <div>
                <dt className="text-[10px] text-slate-400">ثبت‌شده در ۷ روز</dt>
                <dd className="mt-0.5 text-sm font-black text-slate-800">
                  {formatNumber(stats.businesses.last_7d)}
                </dd>
              </div>
              <div>
                <dt className="text-[10px] text-slate-400">نرخ تأیید</dt>
                <dd className="mt-0.5 text-sm font-black text-slate-800">
                  {fa(
                    stats.businesses.total > 0
                      ? Math.round((stats.businesses.approved / stats.businesses.total) * 100)
                      : 0,
                  )}
                  ٪
                </dd>
              </div>
            </dl>
          </ChartCard>
        </div>
      )}

      {/* queues + activity */}
      {data && (
      <div className="grid gap-3 xl:grid-cols-3">
        <div className="space-y-3 xl:col-span-2">
          <ChartCard
            title="کارهای در انتظار شما"
            description="مواردی که برای پیشبرد پلتفرم به بررسی نیاز دارند"
          >
            {(data?.queues ?? []).length === 0 ? (
              <p className="py-6 text-center text-[11px] text-slate-400">صفی برای بررسی وجود ندارد.</p>
            ) : (
              <div className="grid gap-2 sm:grid-cols-2">
                {(data?.queues ?? []).map((item) => (
                  <QueueTile key={item.key} item={item} />
                ))}
              </div>
            )}
          </ChartCard>

          {!stats && (
            <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-5 text-center">
              <p className="text-xs font-medium text-slate-700">
                دسترسی آمار کلی برای شما فعال نیست
              </p>
              <p className="mt-1 text-[11px] leading-6 text-slate-400">
                نمودارها و شمارنده‌ها با دسترسی «مشاهده آمار» نمایش داده می‌شوند. صف‌های کاری مرتبط
                با دسترسی‌های شما در بالا آمده است.
              </p>
            </div>
          )}

          {stats && (
            <div className="grid gap-3 md:grid-cols-2">
              <ChartCard title="عرضه و تقاضای دسته‌ها" description="کسب‌وکار فعال در برابر جستجوهای ثبت‌شده">
                {(data?.top_categories ?? []).length === 0 ? (
                  <p className="py-6 text-center text-[11px] text-slate-400">دسته‌ای ثبت نشده است.</p>
                ) : (
                  <HorizontalBars
                    series={[
                      { key: "businesses", label: "کسب‌وکار", color: "#10b981" },
                      { key: "searches", label: "جستجو", color: "#0ea5e9" },
                    ]}
                    items={(data?.top_categories ?? []).map((row) => ({
                      label: row.name,
                      icon: row.icon,
                      values: { businesses: row.businesses, searches: row.searches },
                    }))}
                    labelWidth={96}
                  />
                )}
              </ChartCard>

              <ChartCard title="ترکیب کاربران" description="تعداد کاربران به تفکیک نقش">
                <div className="space-y-2.5">
                  {(data?.roles ?? []).map((row) => {
                    const total = (data?.roles ?? []).reduce((sum, item) => sum + item.count, 0);
                    const percent = total > 0 ? (row.count / total) * 100 : 0;
                    return (
                      <div key={row.role}>
                        <div className="flex items-center justify-between text-[11px]">
                          <span className="text-slate-600">
                            {roleEmoji(row.role)} {row.label}
                          </span>
                          <span className="flex items-baseline gap-1 font-bold text-slate-800">
                            {formatNumber(row.count)}
                            <span className="text-[9px] font-normal text-slate-400">
                              {fa(Math.round(percent))}٪
                            </span>
                          </span>
                        </div>
                        <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
                          <div
                            className="h-full rounded-full"
                            style={{
                              width: `${Math.max(percent > 0 ? 3 : 0, percent)}%`,
                              backgroundColor: ROLE_COLORS[row.role] ?? "#94a3b8",
                            }}
                          />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </ChartCard>
            </div>
          )}
        </div>

        <ActivityFeed items={data.recent_activity} />
      </div>
      )}

      {/* shortcuts */}
      <ChartCard title="دسترسی سریع" description="پرش به بخش‌های پرکاربرد داشبورد">
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-4 xl:grid-cols-7">
          {shortcuts.map((item) => (
            <Link
              key={item.to}
              to={item.to}
              className="group flex flex-col items-center gap-1.5 rounded-xl border border-slate-200 px-2 py-3 text-center transition-colors hover:border-brand-300 hover:bg-brand-50/40"
            >
              <span className="text-base">{item.icon}</span>
              <span className="text-[10px] font-medium text-slate-600 group-hover:text-brand-700">
                {item.title}
              </span>
            </Link>
          ))}
        </div>
      </ChartCard>

      {user.role !== "superadmin" && user.permissions.length > 0 && (
        <div className="rounded-2xl border border-slate-200 bg-white p-4">
          <p className="text-xs font-bold text-slate-900">دسترسی‌های شما</p>
          <ul className="mt-2 flex flex-wrap gap-1.5">
            {user.permissions.map((code) => (
              <li key={code}>
                <Badge tone="slate">{permissionLabel(code)}</Badge>
              </li>
            ))}
          </ul>
        </div>
      )}
    </section>
  );
}
