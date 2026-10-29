import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { RatingStars } from "@/components/ui/stars";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { useApi, useApiWithMeta } from "@/lib/query";
import {
  DataTable,
  FilterLinks,
  type DataColumn,
  type PageMeta,
} from "@/features/admin/data-table";

interface Row {
  id: string;
  business_id: string;
  business_name?: string | null;
  business_slug?: string | null;
  rating: number;
  text: string | null;
  author_name?: string | null;
  status: string;
  reply?: string | null;
  created_at?: string | null;
}

const STATUS_FILTERS = [
  { label: "همه", value: "" },
  { label: "تأییدشده", value: "approved" },
  { label: "تأییدنشده", value: "pending" },
  { label: "ردشده", value: "rejected" },
];

function statusTone(status: string) {
  if (status === "approved") return "bg-emerald-50 text-emerald-700";
  if (status === "rejected") return "bg-rose-50 text-rose-700";
  return "bg-amber-50 text-amber-700";
}

function statusLabel(status: string) {
  if (status === "approved") return "تأییدشده";
  if (status === "rejected") return "ردشده";
  return "در انتظار";
}

export default function AdminReviewsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();

  const status = params.get("status") ?? "";
  const businessId = params.get("business_id") ?? "";
  const qParam = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);
  const [search, setSearch] = useState(qParam);

  useEffect(() => setSearch(qParam), [qParam]);

  const query = new URLSearchParams({ page: String(page), per_page: "15" });
  if (status) query.set("status", status);
  if (businessId) query.set("business_id", businessId);
  if (qParam) query.set("q", qParam);

  const reviews = useApiWithMeta<{ items: Row[] }, PageMeta>(
    ["admin", "reviews", status, businessId, qParam, page],
    `/admin/reviews?${query.toString()}`,
  );
  const businesses = useApi<{ items: { id: string; name: string }[] }>(
    ["admin", "reviews", "businesses"],
    "/admin/reviews/businesses",
  );

  const items = reviews.data?.data.items ?? [];
  const meta = reviews.data?.meta;

  const setStatus = useMutation({
    mutationFn: ({ id, next }: { id: string; next: string }) =>
      api(`/businesses/reviews/${id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: next }),
      }),
    onSuccess: async (_data, variables) => {
      toast(variables.next === "approved" ? "نظر تأیید شد." : "نظر رد شد.");
      await queryClient.invalidateQueries({ queryKey: ["admin", "reviews"] });
      await queryClient.invalidateQueries({ queryKey: ["reviews"] });
    },
    onError: (error) => toast(errorMessage(error)),
  });

  function updateParams(patch: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    setParams(next);
  }

  function filterHref(value: string) {
    const next = new URLSearchParams();
    if (qParam) next.set("q", qParam);
    if (businessId) next.set("business_id", businessId);
    if (value) next.set("status", value);
    const suffix = next.toString();
    return `/admin/reviews${suffix ? `?${suffix}` : ""}`;
  }

  const columns: DataColumn<Row>[] = [
    {
      key: "business",
      header: "کسب‌وکار / نویسنده",
      cell: (row) => (
        <div>
          <p className="text-sm font-bold text-slate-800">{row.business_name || "—"}</p>
          <p className="mt-0.5 text-[11px] text-slate-500">{row.author_name || "کاربر نومکس"}</p>
        </div>
      ),
    },
    {
      key: "rating",
      header: "امتیاز",
      cell: (row) => <RatingStars rating={row.rating} />,
    },
    {
      key: "text",
      header: "متن نظر",
      cell: (row) => (
        <div className="max-w-xl">
          <p className="text-sm leading-6 text-slate-700">{row.text || "بدون متن"}</p>
          {row.reply && (
            <p className="mt-1 rounded-lg bg-slate-50 px-2 py-1 text-[10px] text-slate-500">
              پاسخ مالک: {row.reply}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      cell: (row) => (
        <span className={`rounded-full px-2 py-0.5 text-[11px] ${statusTone(row.status)}`}>
          {statusLabel(row.status)}
        </span>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-left",
      cell: (row) => (
        <div className="flex flex-wrap justify-end gap-1">
          <Button
            size="sm"
            disabled={setStatus.isPending || row.status === "approved"}
            onClick={() => setStatus.mutate({ id: row.id, next: "approved" })}
          >
            تأیید
          </Button>
          <Button
            size="sm"
            variant="danger"
            disabled={setStatus.isPending || row.status === "rejected"}
            onClick={() => setStatus.mutate({ id: row.id, next: "rejected" })}
          >
            رد
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <div>
        <h1 className="text-lg font-bold">نظرات</h1>
        <p className="mt-1 text-xs text-slate-500">
          همه نظرات عمومی کسب‌وکارها؛ نظرات خصوصی فقط در پنل مالک نمایش داده می‌شوند.
        </p>
      </div>

      <FilterLinks items={STATUS_FILTERS} active={status} hrefFor={filterHref} />

      <DataTable
        columns={columns}
        rows={items}
        rowKey={(row) => row.id}
        loading={reviews.isLoading}
        error={reviews.error ? errorMessage(reviews.error) : null}
        empty="نظری با این فیلتر پیدا نشد."
        minWidthClassName="min-w-[980px]"
        meta={meta ? { page: meta.page, pages: meta.pages, total: meta.total } : undefined}
        onPageChange={(next) => updateParams({ page: String(next) })}
        toolbar={
          <div className="flex flex-wrap items-center gap-2">
            <form
              className="flex min-w-64 flex-1 items-center gap-2"
              onSubmit={(event) => {
                event.preventDefault();
                updateParams({ q: search.trim() || null, page: null });
              }}
            >
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="جستجوی کسب‌وکار، نویسنده یا متن…"
                aria-label="جستجوی نظر"
              />
              <Button size="sm" type="submit" variant="outline">
                جستجو
              </Button>
            </form>
            <select
              value={businessId}
              onChange={(event) =>
                updateParams({ business_id: event.target.value || null, page: null })
              }
              className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700 sm:w-auto"
              aria-label="فیلتر کسب‌وکار"
            >
              <option value="">همه کسب‌وکارها</option>
              {businesses.data?.items.map((business) => (
                <option key={business.id} value={business.id}>
                  {business.name}
                </option>
              ))}
            </select>
          </div>
        }
      />
    </div>
  );
}
