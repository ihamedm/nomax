import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ConfirmSheet } from "@/components/ui/confirm-sheet";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import { formatJalali } from "@/lib/jalali";
import { useApi, useApiWithMeta } from "@/lib/query";
import { useAuth } from "@/stores/auth";
import { AdminModal } from "@/features/admin/AdminModal";
import { DataTable, FilterLinks, type DataColumn, type PageMeta } from "@/features/admin/data-table";
import type {
  Quote,
  QuoteDispatchSummary,
  QuoteOffer,
  QuoteStats,
} from "@/features/quote/types";
import { DispatchProgress } from "@/features/quote/DispatchProgress";
import {
  QUOTE_STATUS_LABELS,
  QUOTE_STATUS_TONES,
  formatToman,
} from "@/features/quote/quote-utils";

const STATUS_FILTERS = [
  { label: "همه", value: "" },
  { label: "فعال", value: "active" },
  { label: "پذیرفته‌شده", value: "accepted" },
  { label: "منقضی", value: "expired" },
  { label: "لغوشده", value: "cancelled" },
];

interface DispatchDelivery {
  business: {
    id: string;
    name: string;
    slug: string;
    is_verified: boolean;
    is_24h: boolean;
    category?: string | null;
  };
  owner: { id: string; name?: string | null; phone: string };
  round: number;
  source: "auto" | "manual" | string;
  sent_at?: string | null;
  seen_at?: string | null;
  responded_at?: string | null;
  offer_status?: string | null;
}

interface DispatchRun {
  id: string;
  round: number;
  trigger: string;
  candidate_count: number;
  delivered_count: number;
  detail: Record<string, unknown>;
  created_at?: string | null;
}

interface AdminQuoteDispatch {
  summary: QuoteDispatchSummary;
  deliveries: DispatchDelivery[];
  runs: DispatchRun[];
  assigned?: { id: string; name: string }[];
  skipped?: string[];
  dispatched?: { id: string; name: string }[];
}

interface AdminBusinessOption {
  id: string;
  name: string;
  status: string;
  is_24h: boolean;
  owner?: { id: string; phone: string; full_name?: string | null } | null;
  category?: { id: number; name: string } | null;
}

const SOURCE_LABELS: Record<string, string> = {
  auto: "خودکار",
  manual: "دستی",
};

const RUN_LABELS: Record<string, string> = {
  initial: "موج اول",
  retry: "توسعه خودکار",
  manual: "افزودن دستی",
  forced: "ارسال اجباری",
};

function StatusPill({ status }: { status: Quote["status"] }) {
  return (
    <Badge tone={QUOTE_STATUS_TONES[status] ?? "slate"}>
      {QUOTE_STATUS_LABELS[status] ?? status}
    </Badge>
  );
}

function StatCard({
  label,
  value,
  hint,
  tone = "text-slate-900",
}: {
  label: string;
  value: string | number;
  hint?: string;
  tone?: string;
}) {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-3.5 text-right">
      <p className="text-[11px] text-slate-400">{label}</p>
      <p className={cn("mt-1 text-xl font-black", tone)}>{toFa(value)}</p>
      {hint && <p className="mt-1 text-[10px] text-slate-400">{hint}</p>}
    </div>
  );
}

function OfferLine({ offer }: { offer: QuoteOffer }) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 px-3 py-2.5">
      <div className="min-w-0">
        <p className="text-xs font-bold text-slate-800">
          {offer.business?.name ?? "کسب‌وکار"}
          {offer.business?.phone_business && (
            <span className="mr-2 font-normal text-slate-400" dir="ltr">
              {offer.business.phone_business}
            </span>
          )}
        </p>
        <p className="mt-0.5 text-[10px] text-slate-400">
          {offer.brand || "بدون برند"}
          {offer.unit ? ` · ${offer.unit}` : ""}
          {offer.message ? ` · ${offer.message}` : ""}
        </p>
      </div>
      <div className="shrink-0 text-left">
        <p className="text-xs font-black text-slate-800">{formatToman(offer.price)}</p>
        <p className="mt-0.5 text-[10px] text-slate-400">
          {offer.status === "accepted"
            ? "پذیرفته‌شده"
            : offer.status === "pending"
              ? "در انتظار"
              : offer.status === "declined"
                ? "ردشده"
                : "منقضی"}
        </p>
      </div>
    </div>
  );
}

export default function AdminQuotesPage() {
  const [params, setParams] = useSearchParams();
  const toast = useToast();
  const queryClient = useQueryClient();
  const user = useAuth((state) => state.user);

  const status = params.get("status") ?? "";
  const qParam = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);
  const [search, setSearch] = useState(qParam);
  const [selected, setSelected] = useState<Quote | null>(null);
  const [cancelTarget, setCancelTarget] = useState<Quote | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);

  useEffect(() => setSearch(qParam), [qParam]);

  const query = new URLSearchParams({ page: String(page), per_page: "15" });
  if (status) query.set("status", status);
  if (qParam) query.set("q", qParam);

  const quotes = useApiWithMeta<{ items: Quote[] }, PageMeta>(
    ["admin", "quotes", status, qParam, page],
    `/admin/quotes?${query.toString()}`,
  );
  const stats = useApi<QuoteStats>(["admin", "quotes", "stats"], "/admin/quotes/stats");
  const detail = useApi<Quote>(
    ["admin", "quote", selected?.id],
    `/admin/quotes/${selected?.id}`,
    { enabled: Boolean(selected) },
  );
  const dispatchDetail = useApi<AdminQuoteDispatch>(
    ["admin", "quote", selected?.id, "dispatch"],
    `/admin/quotes/${selected?.id}/dispatch`,
    { enabled: Boolean(selected) },
  );

  const [dispatchSearch, setDispatchSearch] = useState("");
  const [selectedBusinessIds, setSelectedBusinessIds] = useState<string[]>([]);
  const [showRuns, setShowRuns] = useState(false);

  useEffect(() => {
    setDispatchSearch("");
    setSelectedBusinessIds([]);
    setShowRuns(false);
  }, [selected?.id]);

  const canManage =
    user?.role === "superadmin" || Boolean(user?.permissions.includes("quote.manage"));
  const businessQuery = new URLSearchParams({
    status: "approved",
    q: dispatchSearch.trim(),
    per_page: "8",
  });
  const businessOptions = useApi<{ items: AdminBusinessOption[] }>(
    ["admin", "quote", selected?.id, "assign-search", dispatchSearch.trim()],
    `/admin/businesses?${businessQuery.toString()}`,
    {
      enabled:
        canManage &&
        Boolean(selected) &&
        selected?.status === "active" &&
        dispatchSearch.trim().length >= 2,
    },
  );
  const deliveredBusinessIds = new Set(
    (dispatchDetail.data?.deliveries ?? []).map((item) => item.business.id),
  );

  const cancelMutation = useMutation({
    mutationFn: (id: string) => api(`/admin/quotes/${id}/cancel`, { method: "POST" }),
    onSuccess: async () => {
      toast("درخواست لغو شد و کسب‌وکارهای پیشنهاددهنده مطلع شدند.");
      setCancelOpen(false);
      setCancelTarget(null);
      await queryClient.invalidateQueries({ queryKey: ["admin", "quotes"] });
      await queryClient.invalidateQueries({ queryKey: ["admin", "quote"] });
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const assignMutation = useMutation({
    mutationFn: (businessIds: string[]) =>
      api<AdminQuoteDispatch>(`/admin/quotes/${selected?.id}/assign`, {
        method: "POST",
        body: JSON.stringify({ business_ids: businessIds }),
      }),
    onSuccess: async (result) => {
      const assigned = result.assigned?.length ?? 0;
      if (assigned > 0) {
        toast(
          `${toFa(assigned)} کسب‌وکار به این استعلام اضافه شد و صاحبان آن‌ها مطلع شدند.`,
        );
      } else {
        toast("کسب‌وکار انتخاب‌شده قبلاً این استعلام را دریافت کرده بود.");
      }
      setSelectedBusinessIds([]);
      await queryClient.invalidateQueries({ queryKey: ["admin", "quotes"] });
      await queryClient.invalidateQueries({ queryKey: ["admin", "quote"] });
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const forceDispatchMutation = useMutation({
    mutationFn: () =>
      api<AdminQuoteDispatch>(`/admin/quotes/${selected?.id}/dispatch-now`, {
        method: "POST",
      }),
    onSuccess: async (result) => {
      const count = result.dispatched?.length ?? 0;
      toast(
        count > 0
          ? `موج بعدی برای ${toFa(count)} کسب‌وکار ارسال شد.`
          : "کسب‌وکار جدیدی برای ارسال وجود ندارد یا پیشنهاد در انتظار پاسخ است.",
      );
      await queryClient.invalidateQueries({ queryKey: ["admin", "quotes"] });
      await queryClient.invalidateQueries({ queryKey: ["admin", "quote"] });
    },
    onError: (error) => toast(errorMessage(error)),
  });

  function toggleBusiness(id: string) {
    setSelectedBusinessIds((current) =>
      current.includes(id)
        ? current.filter((item) => item !== id)
        : [...current, id].slice(0, 20),
    );
  }

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
    if (value) next.set("status", value);
    const suffix = next.toString();
    return `/admin/quotes${suffix ? `?${suffix}` : ""}`;
  }

  const columns: DataColumn<Quote>[] = [
    {
      key: "quote",
      header: "درخواست",
      cell: (row) => (
        <div className="min-w-48">
          <p className="text-sm font-bold text-slate-800">{row.title}</p>
          <p className="mt-0.5 text-[11px] text-slate-400">
            {row.category?.icon} {row.category?.name ?? "بدون دسته"}
            {row.is_urgent ? " · فوری" : ""}
          </p>
        </div>
      ),
    },
    {
      key: "customer",
      header: "مشتری",
      cell: (row) => (
        <div>
          <p className="text-xs font-medium text-slate-700">{row.customer?.name ?? "—"}</p>
          <p className="mt-0.5 text-[10px] text-slate-400" dir="ltr">
            {row.customer?.phone ?? "—"}
          </p>
        </div>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      cell: (row) => <StatusPill status={row.status} />,
    },
    {
      key: "offers",
      header: "پیشنهادها",
      cell: (row) => (
        <div>
          <p className="text-xs font-bold text-slate-700">{toFa(row.offers_count)}</p>
          {row.accepted_offer?.business && (
            <p className="mt-0.5 max-w-40 truncate text-[10px] text-brand-600">
              {row.accepted_offer.business.name}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "dates",
      header: "زمان",
      cell: (row) => (
        <div className="text-[10px] leading-5 text-slate-400">
          <p>ثبت: {row.created_at ? formatJalali(row.created_at) : "—"}</p>
          <p>پایان: {row.expires_at ? formatJalali(row.expires_at) : "—"}</p>
        </div>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-left",
      cell: (row) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="outline" onClick={() => setSelected(row)}>
            جزئیات
          </Button>
          {canManage && row.status === "active" && (
            <Button
              size="sm"
              variant="danger"
              onClick={() => {
                setCancelTarget(row);
                setCancelOpen(true);
              }}
            >
              لغو
            </Button>
          )}
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-bold">استعلام‌های قیمت</h1>
          <p className="mt-1 text-xs text-slate-500">
            وضعیت درخواست‌ها، پیشنهادهای بازار و نرخ تبدیل به مشتری نهایی.
          </p>
        </div>
        <span className="rounded-full bg-slate-200/70 px-2.5 py-1 text-[10px] text-slate-500">
          فقط خواندن و مدیریت استعلام
        </span>
      </div>

      <div className="grid grid-cols-2 gap-2 lg:grid-cols-5">
        <StatCard label="کل درخواست‌ها" value={stats.data?.total ?? 0} />
        <StatCard
          label="فعال"
          value={stats.data?.active ?? 0}
          hint={`${toFa(stats.data?.urgent_active ?? 0)} فوری`}
          tone="text-brand-600"
        />
        <StatCard
          label="پذیرفته‌شده"
          value={stats.data?.accepted ?? 0}
          hint={`نرخ تبدیل ${toFa(stats.data?.acceptance_rate ?? 0)}٪`}
          tone="text-emerald-600"
        />
        <StatCard label="کل پیشنهادها" value={stats.data?.offers_total ?? 0} />
        <StatCard
          label="در انتظار پاسخ"
          value={stats.data?.pending_offers ?? 0}
          tone="text-amber-600"
        />
      </div>

      <FilterLinks items={STATUS_FILTERS} active={status} hrefFor={filterHref} />

      <DataTable
        columns={columns}
        rows={quotes.data?.data.items ?? []}
        rowKey={(row) => row.id}
        loading={quotes.isLoading}
        error={quotes.error ? errorMessage(quotes.error) : null}
        empty="درخواستی با این فیلتر پیدا نشد."
        minWidthClassName="min-w-[980px]"
        meta={
          quotes.data?.meta
            ? {
                page: quotes.data.meta.page,
                pages: quotes.data.meta.pages,
                total: quotes.data.meta.total,
              }
            : undefined
        }
        onPageChange={(next) => updateParams({ page: String(next) })}
        toolbar={
          <form
            className="flex max-w-md items-center gap-2"
            onSubmit={(event) => {
              event.preventDefault();
              updateParams({ q: search.trim() || null, page: null });
            }}
          >
            <Input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="جستجوی عنوان، مشتری یا شماره…"
              aria-label="جستجوی استعلام"
            />
            <Button size="sm" type="submit" variant="outline">
              جستجو
            </Button>
          </form>
        }
      />

      {selected && (
        <AdminModal
          title="جزئیات استعلام"
          className="max-w-4xl"
          onClose={() => {
            setSelected(null);
            setCancelOpen(false);
            setCancelTarget(null);
          }}
        >
          {detail.isLoading && (
            <p className="py-8 text-center text-xs text-slate-400">در حال بارگذاری…</p>
          )}
          {detail.error && (
            <p className="py-6 text-center text-xs text-rose-600">{errorMessage(detail.error)}</p>
          )}
          {detail.data && (
            <div className="space-y-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-base font-black text-slate-900">{detail.data.title}</p>
                  <p className="mt-1 text-[11px] text-slate-400">
                    {detail.data.category?.name ?? "بدون دسته"}
                    {detail.data.subcategory ? ` › ${detail.data.subcategory.name}` : ""}
                  </p>
                </div>
                <StatusPill status={detail.data.status} />
              </div>

              {detail.data.description && (
                <p className="rounded-xl bg-slate-50 p-3 text-xs leading-6 text-slate-600">
                  {detail.data.description}
                </p>
              )}

              <div className="grid gap-2 text-xs sm:grid-cols-2">
                <div className="rounded-xl border border-slate-200 p-3">
                  <p className="text-[10px] text-slate-400">مشتری</p>
                  <p className="mt-1 font-bold text-slate-800">
                    {detail.data.customer?.name ?? "—"}
                  </p>
                  <p className="mt-0.5 text-slate-500" dir="ltr">
                    {detail.data.customer?.phone ?? detail.data.customer_phone ?? "—"}
                  </p>
                </div>
                <div className="rounded-xl border border-slate-200 p-3">
                  <p className="text-[10px] text-slate-400">آدرس</p>
                  <p className="mt-1 leading-6 text-slate-700">{detail.data.address}</p>
                </div>
              </div>

              <div className="flex flex-wrap gap-4 text-[11px] text-slate-500">
                <span>ثبت: {formatJalali(detail.data.created_at ?? "")}</span>
                <span>پایان: {formatJalali(detail.data.expires_at ?? "")}</span>
                <span>{toFa(detail.data.offers_count)} پیشنهاد</span>
                {detail.data.is_urgent && <Badge tone="amber">فوری</Badge>}
              </div>

              <div>
                <p className="mb-2 text-xs font-bold text-slate-800">پیشنهادهای ثبت‌شده</p>
                <div className="space-y-2">
                  {detail.data.offers?.length ? (
                    detail.data.offers.map((offer) => (
                      <OfferLine key={offer.id} offer={offer} />
                    ))
                  ) : (
                    <p className="rounded-xl border border-dashed border-slate-200 p-4 text-center text-[11px] text-slate-400">
                      هنوز پیشنهادی ثبت نشده است.
                    </p>
                  )}
                </div>
              </div>

              {dispatchDetail.isLoading && (
                <p className="rounded-xl bg-slate-50 p-3 text-center text-[11px] text-slate-400">
                  در حال دریافت وضعیت ارسال…
                </p>
              )}
              {dispatchDetail.error && (
                <p className="text-[11px] text-rose-600">
                  {errorMessage(dispatchDetail.error)}
                </p>
              )}
              {dispatchDetail.data && (
                <div className="space-y-3 rounded-2xl border border-slate-200 bg-slate-50/60 p-3">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="text-xs font-black text-slate-800">گردش ارسال به صاحبان</p>
                      <p className="mt-0.5 text-[10px] text-slate-400">
                        هر موج فقط به صاحبان تازه ارسال می‌شود؛ صاحبان قبلی تکرار نمی‌شوند.
                      </p>
                    </div>
                    {canManage && detail.data.status === "active" && (
                      <Button
                        size="sm"
                        variant="outline"
                        loading={forceDispatchMutation.isPending}
                        onClick={() => forceDispatchMutation.mutate()}
                      >
                        ارسال موج بعدی
                      </Button>
                    )}
                  </div>

                  <DispatchProgress dispatch={dispatchDetail.data.summary} />

                  <div className="grid grid-cols-3 gap-2">
                    {[
                      ["ارسال‌شده", dispatchDetail.data.summary?.delivered_count ?? 0, "text-brand-700"],
                      ["مشاهده‌شده", dispatchDetail.data.summary?.seen_count ?? 0, "text-amber-700"],
                      ["پیشنهاد", dispatchDetail.data.summary?.offers_count ?? 0, "text-emerald-700"],
                    ].map(([label, value, tone]) => (
                      <div key={String(label)} className="rounded-xl bg-white px-2.5 py-2 text-center">
                        <p className="text-[9px] text-slate-400">{label}</p>
                        <p className={cn("mt-0.5 text-sm font-black", String(tone))}>{toFa(Number(value))}</p>
                      </div>
                    ))}
                  </div>

                  <div>
                    <p className="mb-1.5 text-[11px] font-bold text-slate-700">
                      کسب‌وکارهای مطلع‌شده ({toFa(dispatchDetail.data.deliveries.length)})
                    </p>
                    <div className="max-h-56 space-y-1.5 overflow-y-auto pl-0.5">
                      {dispatchDetail.data.deliveries.length === 0 && (
                        <p className="rounded-xl border border-dashed border-slate-200 bg-white p-3 text-center text-[10px] text-slate-400">
                          هنوز به هیچ کسب‌وکاری ارسال نشده است.
                        </p>
                      )}
                      {dispatchDetail.data.deliveries.map((delivery) => (
                        <div
                          key={`${delivery.business.id}-${delivery.round}`}
                          className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-slate-200 bg-white px-2.5 py-2"
                        >
                          <div className="min-w-0">
                            <p className="truncate text-[11px] font-bold text-slate-800">
                              {delivery.business.name}
                              {delivery.business.is_verified && (
                                <span className="mr-1 text-[9px] font-normal text-brand-600">تأییدشده</span>
                              )}
                            </p>
                            <p className="mt-0.5 text-[9px] text-slate-400">
                              {delivery.owner.name || "صاحب کسب‌وکار"} ·{" "}
                              <span dir="ltr">{delivery.owner.phone}</span> ·{" "}
                              {SOURCE_LABELS[delivery.source] ?? delivery.source} · موج {toFa(delivery.round)}
                            </p>
                          </div>
                          <div className="flex shrink-0 items-center gap-1">
                            <Badge tone={delivery.seen_at ? "brand" : "slate"}>
                              {delivery.seen_at ? "مشاهده شد" : "دیده‌نشده"}
                            </Badge>
                            {delivery.offer_status && (
                              <Badge
                                tone={
                                  delivery.offer_status === "pending"
                                    ? "amber"
                                    : delivery.offer_status === "accepted"
                                      ? "brand"
                                      : "slate"
                                }
                              >
                                {delivery.offer_status === "pending"
                                  ? "پیشنهاد ثبت‌شده"
                                  : delivery.offer_status === "accepted"
                                    ? "پذیرفته‌شده"
                                    : delivery.offer_status === "declined"
                                      ? "ردشده"
                                      : "منقضی"}
                              </Badge>
                            )}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>

                  {canManage && detail.data.status === "active" && (
                    <div className="rounded-xl border border-brand-100 bg-brand-50/50 p-2.5">
                      <p className="text-[11px] font-black text-brand-800">افزودن دستی صاحب کسب‌وکار</p>
                      <p className="mt-0.5 text-[9px] leading-5 text-brand-700/70">
                        جستجو بر اساس نام کسب‌وکار؛ محدودیت دسته‌بندی و شعاع برای افزودن دستی اعمال نمی‌شود.
                      </p>
                      <Input
                        value={dispatchSearch}
                        onChange={(event) => setDispatchSearch(event.target.value)}
                        placeholder="نام کسب‌وکار را بنویسید…"
                        aria-label="جستجوی کسب‌وکار برای ارسال دستی"
                        className="mt-2 h-9 bg-white text-xs"
                      />
                      {dispatchSearch.trim().length >= 2 && (
                        <div className="mt-1.5 max-h-44 space-y-1 overflow-y-auto">
                          {businessOptions.isLoading && (
                            <p className="py-2 text-center text-[10px] text-slate-400">در حال جستجو…</p>
                          )}
                          {!businessOptions.isLoading &&
                            (businessOptions.data?.items.length ?? 0) === 0 && (
                              <p className="py-2 text-center text-[10px] text-slate-400">
                                کسب‌وکار تأییدشده‌ای با این نام پیدا نشد.
                              </p>
                            )}
                          {businessOptions.data?.items.map((business) => {
                            const alreadySent = deliveredBusinessIds.has(business.id);
                            const checked = selectedBusinessIds.includes(business.id);
                            return (
                              <label
                                key={business.id}
                                className={cn(
                                  "flex items-center justify-between gap-2 rounded-lg border bg-white px-2 py-1.5",
                                  alreadySent
                                    ? "border-slate-100 opacity-60"
                                    : checked
                                      ? "border-brand-300 ring-1 ring-brand-100"
                                      : "border-slate-200",
                                )}
                              >
                                <span className="flex min-w-0 items-center gap-2">
                                  <input
                                    type="checkbox"
                                    checked={checked}
                                    disabled={alreadySent}
                                    onChange={() => toggleBusiness(business.id)}
                                    className="h-3.5 w-3.5 accent-brand-600"
                                  />
                                  <span className="min-w-0">
                                    <span className="block truncate text-[10px] font-bold text-slate-700">
                                      {business.name}
                                    </span>
                                    <span className="mt-0.5 block text-[9px] text-slate-400">
                                      {business.owner?.full_name || "صاحب کسب‌وکار"} ·{" "}
                                      <span dir="ltr">{business.owner?.phone}</span>
                                      {business.category ? ` · ${business.category.name}` : ""}
                                    </span>
                                  </span>
                                </span>
                                {alreadySent && (
                                  <span className="shrink-0 text-[9px] text-slate-400">قبلاً ارسال شده</span>
                                )}
                              </label>
                            );
                          })}
                        </div>
                      )}
                      <div className="mt-2 flex items-center justify-between gap-2">
                        <span className="text-[9px] text-slate-500">
                          {selectedBusinessIds.length > 0
                            ? `${toFa(selectedBusinessIds.length)} کسب‌وکار انتخاب شده`
                            : "حداقل یک کسب‌وکار انتخاب کنید"}
                        </span>
                        <Button
                          size="sm"
                          loading={assignMutation.isPending}
                          disabled={selectedBusinessIds.length === 0}
                          onClick={() => assignMutation.mutate(selectedBusinessIds)}
                        >
                          افزودن و ارسال
                        </Button>
                      </div>
                    </div>
                  )}

                  {dispatchDetail.data.runs.length > 0 && (
                    <div>
                      <button
                        type="button"
                        onClick={() => setShowRuns((current) => !current)}
                        className="text-[10px] font-bold text-slate-500"
                      >
                        {showRuns ? "پنهان کردن تاریخچه ارسال" : "نمایش تاریخچه ارسال"}
                      </button>
                      {showRuns && (
                        <div className="mt-1.5 space-y-1">
                          {dispatchDetail.data.runs.map((run) => (
                            <div
                              key={run.id}
                              className="flex flex-wrap items-center justify-between gap-1 rounded-lg bg-white px-2 py-1.5 text-[9px] text-slate-500"
                            >
                              <span>
                                {RUN_LABELS[run.trigger] ?? run.trigger} · موج {toFa(run.round)}
                              </span>
                              <span>
                                {toFa(run.candidate_count)} کاندید · {toFa(run.delivered_count)} ارسال
                              </span>
                              <span className="text-slate-400">
                                {run.created_at ? formatJalali(run.created_at) : "—"}
                              </span>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              )}

              {canManage && detail.data.status === "active" && (
                <Button
                  variant="danger"
                  className="w-full"
                  onClick={() => {
                    setCancelTarget(detail.data);
                    setCancelOpen(true);
                  }}
                >
                  لغو درخواست
                </Button>
              )}
            </div>
          )}
        </AdminModal>
      )}

      <ConfirmSheet
        open={cancelOpen && cancelTarget !== null}
        title="لغو درخواست استعلام"
        description="این درخواست لغو می‌شود، پیشنهادهای در انتظار منقضی می‌شوند و به کسب‌وکارها اطلاع داده می‌شود. ادامه می‌دهید؟"
        confirmLabel="لغو درخواست"
        tone="rose"
        loading={cancelMutation.isPending}
        onClose={() => {
          setCancelOpen(false);
          setCancelTarget(null);
        }}
        onConfirm={() => cancelTarget && cancelMutation.mutate(cancelTarget.id)}
      />
    </div>
  );
}
