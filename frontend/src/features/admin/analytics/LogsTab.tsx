import { useState } from "react";
import { useSearchParams } from "react-router-dom";

import { Spinner } from "@/components/ui/button";
import { DataTable, type DataColumn, type PageMeta } from "@/features/admin/data-table";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import { formatJalaliDateTime } from "@/lib/jalali";
import { useApi, useApiWithMeta } from "@/lib/query";
import type { ActivityLog, ActivityLogSummary, ActivityType } from "./types";
import { ChartCard, DonutChart, LineChart } from "./charts";
import { shortDateLabel } from "./analytics-utils";

const EVENT_META: Record<
  ActivityType,
  { label: string; color: string; className: string; icon: string }
> = {
  search: { label: "جستجو", color: "#10a56f", className: "bg-brand-50 text-brand-700", icon: "🔎" },
  user_registered: {
    label: "ثبت‌نام",
    color: "#7c3aed",
    className: "bg-violet-50 text-violet-700",
    icon: "👤",
  },
  business_created: {
    label: "ثبت کسب‌وکار",
    color: "#0284c7",
    className: "bg-sky-50 text-sky-700",
    icon: "🏪",
  },
  review_created: {
    label: "ثبت نظر",
    color: "#d97706",
    className: "bg-amber-50 text-amber-700",
    icon: "★",
  },
  quote_requested: {
    label: "درخواست قیمت",
    color: "#0f766e",
    className: "bg-teal-50 text-teal-700",
    icon: "⌕",
  },
  quote_offer: {
    label: "ارسال پیشنهاد",
    color: "#2563eb",
    className: "bg-blue-50 text-blue-700",
    icon: "✉",
  },
  quote_seen: {
    label: "مشاهده استعلام",
    color: "#64748b",
    className: "bg-slate-100 text-slate-600",
    icon: "👁",
  },
  quote_chosen: {
    label: "انتخاب پیشنهاد",
    color: "#e11d48",
    className: "bg-rose-50 text-rose-700",
    icon: "✓",
  },
};

const FILTERS: Array<{ value: string; label: string }> = [
  { value: "", label: "همه رویدادها" },
  { value: "search", label: "جستجو" },
  { value: "quote_requested", label: "درخواست قیمت" },
  { value: "quote_offer", label: "ارسال پیشنهاد" },
  { value: "quote_seen", label: "مشاهده استعلام" },
  { value: "quote_chosen", label: "انتخاب پیشنهاد" },
  { value: "user_registered", label: "ثبت‌نام" },
  { value: "business_created", label: "ثبت کسب‌وکار" },
  { value: "review_created", label: "ثبت نظر" },
];

export function LogsTab() {
  const [params, setParams] = useSearchParams();
  const type = params.get("type") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);
  const [perPage] = useState(25);

  const query = new URLSearchParams({ page: String(page), per_page: String(perPage) });
  if (type) query.set("type", type);

  const summary = useApi<ActivityLogSummary>(
    ["admin", "analytics", "logs", "summary"],
    "/admin/analytics/logs/summary",
  );
  const logs = useApiWithMeta<{ items: ActivityLog[] }, PageMeta>(
    ["admin", "analytics", "logs", type, page],
    `/admin/analytics/logs?${query.toString()}`,
  );

  function setParam(patch: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    setParams(next);
  }

  const daily = (summary.data?.daily ?? []).map((item) => ({
    label: shortDateLabel(item.date),
    total: item.total,
  }));
  const typeItems = (summary.data?.by_type ?? []).map((item) => ({
    label: `${EVENT_META[item.type]?.icon ?? "•"} ${EVENT_META[item.type]?.label ?? item.type}`,
    value: item.count,
    color: EVENT_META[item.type]?.color ?? "#94a3b8",
  }));

  const columns: DataColumn<ActivityLog>[] = [
    {
      key: "time",
      header: "زمان",
      cell: (row) => (
        <span className="whitespace-nowrap text-[10px] text-slate-500">
          {row.occurred_at ? formatJalaliDateTime(row.occurred_at) : "—"}
        </span>
      ),
    },
    {
      key: "type",
      header: "نوع رویداد",
      cell: (row) => {
        const meta = EVENT_META[row.type];
        return (
          <span
            className={cn(
              "inline-flex items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[10px]",
              meta?.className ?? "bg-slate-100 text-slate-600",
            )}
          >
            <span aria-hidden>{meta?.icon ?? "•"}</span>
            {meta?.label ?? row.type}
          </span>
        );
      },
    },
    {
      key: "user",
      header: "کاربر",
      cell: (row) => (
        <div>
          <p className="text-[11px] font-medium text-slate-700">{row.user_name}</p>
          {row.user_id && (
            <p className="mt-0.5 max-w-32 truncate text-[9px] text-slate-400" dir="ltr">
              {row.user_id}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "event",
      header: "رویداد",
      cell: (row) => (
        <div className="min-w-48">
          <p className="text-[11px] font-bold text-slate-800">{row.title}</p>
          {row.detail && <p className="mt-0.5 text-[10px] text-slate-500">{row.detail}</p>}
        </div>
      ),
    },
    {
      key: "target",
      header: "شناسه",
      cell: (row) => (
        <span className="block max-w-36 truncate text-[9px] text-slate-400" dir="ltr" title={row.entity_id}>
          {row.entity_type}: {row.entity_id}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="grid gap-3 xl:grid-cols-3">
        <ChartCard
          title="روند رویدادهای کاربران"
          description="تعداد کل رویدادها در ۱۴ روز اخیر"
          className="xl:col-span-2"
        >
          <LineChart
            data={daily}
            series={[{ key: "total", label: "رویداد", color: "#10a56f" }]}
            height={210}
          />
        </ChartCard>

        <ChartCard title="ترکیب رویدادها" description="توزیع کل رویدادها بر اساس نوع">
          {summary.isLoading ? (
            <div className="flex justify-center py-10 text-brand-600">
              <Spinner />
            </div>
          ) : summary.error ? (
            <p className="py-8 text-center text-xs text-rose-600">{errorMessage(summary.error)}</p>
          ) : typeItems.length === 0 ? (
            <p className="py-8 text-center text-xs text-slate-400">هنوز رویدادی ثبت نشده است.</p>
          ) : (
            <DonutChart
              items={typeItems}
              centerValue={toFa(summary.data?.total ?? 0)}
              centerLabel="رویداد"
            />
          )}
        </ChartCard>
      </div>

      <section className="space-y-2">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h2 className="text-sm font-black text-slate-900">لاگ خام رویدادها</h2>
            <p className="mt-1 text-[11px] text-slate-400">
              جستجوها، ثبت‌نام‌ها، کسب‌وکارها، نظرات و چرخه استعلام؛ جدیدترین رویدادها ابتدا.
            </p>
          </div>
          <select
            value={type}
            onChange={(event) => setParam({ type: event.target.value || null, page: null })}
            className="h-9 rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-700"
            aria-label="فیلتر نوع رویداد"
          >
            {FILTERS.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </div>

        <DataTable
          columns={columns}
          rows={logs.data?.data.items ?? []}
          rowKey={(row) => row.id}
          loading={logs.isLoading}
          error={logs.error ? errorMessage(logs.error) : null}
          empty="رویدادی با این فیلتر ثبت نشده است."
          minWidthClassName="min-w-[900px]"
          meta={
            logs.data?.meta
              ? {
                  page: logs.data.meta.page,
                  pages: logs.data.meta.pages,
                  total: logs.data.meta.total,
                }
              : undefined
          }
          onPageChange={(next) => setParam({ page: String(next) })}
        />
      </section>
    </div>
  );
}
