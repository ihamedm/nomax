import { useMemo, useState } from "react";

import { Input } from "@/components/ui/input";
import { RatingStars } from "@/components/ui/stars";
import { DataTable, type DataColumn } from "@/features/admin/data-table";
import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import type { BusinessPerformance, BusinessPerformanceRow } from "./types";
import { formatNumber } from "./analytics-utils";

type SortKey =
  | "name"
  | "category"
  | "views"
  | "suggested"
  | "accepted"
  | "response"
  | "rating"
  | "negative"
  | "status";

const STATUS_RANK: Record<BusinessPerformanceRow["status"], number> = {
  critical: 0,
  watch: 1,
  low_response: 2,
  normal: 3,
  top: 4,
};

const STATUS_CLASS: Record<BusinessPerformanceRow["status"], string> = {
  critical: "bg-rose-50 text-rose-700",
  watch: "bg-amber-50 text-amber-700",
  low_response: "bg-orange-50 text-orange-700",
  normal: "bg-slate-100 text-slate-600",
  top: "bg-brand-50 text-brand-700",
};

function ResponseBar({ value }: { value: number }) {
  return (
    <div className="min-w-28">
      <div className="flex items-center justify-between gap-2 text-[10px]">
        <span
          className={cn(
            "font-bold",
            value >= 70 ? "text-brand-700" : value >= 40 ? "text-amber-700" : "text-rose-700",
          )}
        >
          {toFa(value)}٪
        </span>
      </div>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn(
            "h-full rounded-full",
            value >= 70 ? "bg-brand-500" : value >= 40 ? "bg-amber-500" : "bg-rose-500",
          )}
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
    </div>
  );
}

function NegativeBar({ value }: { value: number }) {
  return (
    <div className="min-w-24">
      <span
        className={cn(
          "text-[10px] font-bold",
          value >= 25 ? "text-rose-700" : value > 0 ? "text-amber-700" : "text-slate-400",
        )}
      >
        {toFa(value)}٪
      </span>
      <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-slate-100">
        <div
          className={cn(
            "h-full rounded-full",
            value >= 25 ? "bg-rose-500" : value > 0 ? "bg-amber-400" : "bg-slate-200",
          )}
          style={{ width: `${Math.min(100, value)}%` }}
        />
      </div>
    </div>
  );
}

export function BusinessesTab({ data }: { data: BusinessPerformance }) {
  const [search, setSearch] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("views");
  const [sortDirection, setSortDirection] = useState<"asc" | "desc">("desc");

  function toggleSort(key: string) {
    const next = key as SortKey;
    if (next === sortKey) {
      setSortDirection((current) => (current === "desc" ? "asc" : "desc"));
      return;
    }
    setSortKey(next);
    setSortDirection(next === "name" || next === "category" ? "asc" : "desc");
  }

  const rows = useMemo(() => {
    const term = search.trim();
    const filtered = term
      ? data.items.filter((row) =>
          [row.name, row.category?.name, row.subcategory?.name]
            .filter(Boolean)
            .some((value) => String(value).includes(term)),
        )
      : data.items;
    const sorted = [...filtered].sort((a, b) => {
      let comparison = 0;
      switch (sortKey) {
        case "name":
          comparison = a.name.localeCompare(b.name, "fa");
          break;
        case "category":
          comparison = (a.category?.name ?? "").localeCompare(b.category?.name ?? "", "fa");
          break;
        case "views":
          comparison = a.view_count - b.view_count;
          break;
        case "suggested":
          comparison = a.quotes_suggested - b.quotes_suggested;
          break;
        case "accepted":
          comparison = a.quotes_accepted - b.quotes_accepted;
          break;
        case "response":
          comparison = a.response_rate - b.response_rate;
          break;
        case "rating":
          comparison = a.rating_avg - b.rating_avg;
          break;
        case "negative":
          comparison = a.negative_rate - b.negative_rate;
          break;
        case "status":
          comparison = STATUS_RANK[a.status] - STATUS_RANK[b.status];
          break;
      }
      return sortDirection === "asc" ? comparison : -comparison;
    });
    return sorted;
  }, [data.items, search, sortDirection, sortKey]);

  const columns: DataColumn<BusinessPerformanceRow>[] = [
    {
      key: "name",
      header: "کسب‌وکار",
      sortable: true,
      cell: (row) => (
        <div className="min-w-40">
          <p className="text-xs font-bold text-slate-800">{row.name}</p>
          <p className="mt-0.5 text-[10px] text-slate-400" dir="ltr">
            /businesses/{row.slug}
          </p>
        </div>
      ),
    },
    {
      key: "category",
      header: "دسته / زیردسته",
      sortable: true,
      cell: (row) => (
        <div className="text-[11px] leading-5">
          <p className="text-slate-700">
            {row.category?.icon} {row.category?.name ?? "بدون دسته"}
          </p>
          <p className="text-[10px] text-slate-400">{row.subcategory?.name ?? "بدون زیردسته"}</p>
        </div>
      ),
    },
    {
      key: "views",
      header: "بازدید",
      sortable: true,
      cell: (row) => (
        <span className="text-xs font-bold text-slate-700">{formatNumber(row.view_count)}</span>
      ),
    },
    {
      key: "suggested",
      header: "پیشنهاد ارسالی",
      sortable: true,
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.quotes_suggested)}</span>,
    },
    {
      key: "accepted",
      header: "پیشنهاد پذیرفته",
      sortable: true,
      cell: (row) => <span className="text-xs text-slate-700">{toFa(row.quotes_accepted)}</span>,
    },
    {
      key: "response",
      header: "نرخ پاسخ",
      sortable: true,
      cell: (row) => <ResponseBar value={row.response_rate} />,
    },
    {
      key: "rating",
      header: "امتیاز",
      sortable: true,
      cell: (row) => (
        <div className="min-w-24">
          {row.rating_count > 0 ? (
            <>
              <RatingStars rating={row.rating_avg} />
              <p className="mt-0.5 text-[10px] text-slate-400">
                {toFa(row.rating_avg)} از {toFa(row.rating_count)} نظر
              </p>
            </>
          ) : (
            <span className="text-[10px] text-slate-400">بدون نظر</span>
          )}
        </div>
      ),
    },
    {
      key: "negative",
      header: "نرخ منفی",
      sortable: true,
      cell: (row) => <NegativeBar value={row.negative_rate} />,
    },
    {
      key: "status",
      header: "وضعیت",
      sortable: true,
      cell: (row) => (
        <span className={cn("inline-flex rounded-full px-2 py-0.5 text-[10px]", STATUS_CLASS[row.status])}>
          {row.status_label}
        </span>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-sm font-black text-slate-900">عملکرد کسب‌وکارها</h2>
          <p className="mt-1 text-[11px] text-slate-400">
            بازدید، پیشنهادهای ارسالی و پذیرفته‌شده، نرخ پاسخ، امتیاز و نرخ نظرات منفی. برای مرتب‌سازی روی سرستون‌ها کلیک کنید.
          </p>
        </div>
        <Input
          value={search}
          onChange={(event) => setSearch(event.target.value)}
          placeholder="جستجوی کسب‌وکار یا دسته…"
          aria-label="جستجوی عملکرد کسب‌وکار"
          className="h-9 w-full max-w-64 text-xs"
        />
      </div>

      <DataTable
        columns={columns}
        rows={rows}
        rowKey={(row) => row.id}
        empty="کسب‌وکاری با این مشخصات پیدا نشد."
        minWidthClassName="min-w-[1120px]"
        sortKey={sortKey}
        sortDirection={sortDirection}
        onSort={toggleSort}
      />
    </div>
  );
}
