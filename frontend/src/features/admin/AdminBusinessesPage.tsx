import { useEffect, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { ConfirmSheet } from "@/components/ui/confirm-sheet";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fa, formatPhone, formatRating } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";
import { useApi, useApiWithMeta } from "@/lib/query";
import { useAuth } from "@/stores/auth";
import { AdminModal } from "@/features/admin/AdminModal";
import { AdminBusinessWizard, type AdminBusinessDetail } from "@/features/admin/AdminBusinessWizard";
import { DataTable, type DataColumn } from "@/features/admin/data-table";

type BusinessStatus = "pending" | "approved" | "rejected";

interface Owner {
  id: string;
  phone: string;
  full_name?: string | null;
}

interface CategoryRef {
  id: number;
  slug: string;
  name: string;
  icon?: string;
}

interface BusinessRow {
  id: string;
  name: string;
  slug: string;
  status: BusinessStatus;
  is_verified: boolean;
  is_24h: boolean;
  short_description: string;
  description?: string | null;
  address: string;
  phone_business?: string | null;
  instagram?: string | null;
  geo?: { lat: number; lng: number } | null;
  category: CategoryRef | null;
  subcategory: CategoryRef | null;
  rating_avg: number;
  rating_count: number;
  profile_image_url?: string | null;
  rejection_reason?: string | null;
  owner: Owner | null;
  created_at?: string | null;
  updated_at?: string | null;
  deleted_at?: string | null;
}

interface Meta {
  page: number;
  per_page: number;
  total: number;
  pages: number;
}

const FILTERS: Array<{ label: string; value: string }> = [
  { label: "همه", value: "" },
  { label: "در انتظار تأیید", value: "pending" },
  { label: "تأییدشده", value: "approved" },
  { label: "ردشده", value: "rejected" },
  { label: "سبد حذف‌شده‌ها", value: "trash" },
];

const STATUS_META: Record<BusinessStatus, { label: string; className: string }> = {
  pending: { label: "در انتظار", className: "bg-amber-50 text-amber-700" },
  approved: { label: "تأییدشده", className: "bg-emerald-50 text-emerald-700" },
  rejected: { label: "ردشده", className: "bg-rose-50 text-rose-700" },
};

function StatusPill({ status }: { status: BusinessStatus }) {
  const meta = STATUS_META[status] ?? STATUS_META.pending;
  return (
    <span className={cn("inline-flex rounded-full px-2 py-0.5 text-[11px] font-medium", meta.className)}>
      {meta.label}
    </span>
  );
}

function ActionButton({
  children,
  onClick,
  disabled,
  tone = "slate",
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tone?: "slate" | "brand" | "green" | "rose";
}) {
  const tones = {
    slate: "border border-slate-200 bg-white text-slate-700 hover:bg-slate-50",
    brand: "bg-brand-600 text-white hover:bg-brand-700",
    green: "bg-emerald-600 text-white hover:bg-emerald-700",
    rose: "bg-rose-600 text-white hover:bg-rose-700",
  } as const;
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "rounded-lg px-2.5 py-1.5 text-xs disabled:pointer-events-none disabled:opacity-50",
        tones[tone],
      )}
    >
      {children}
    </button>
  );
}

function RowLink({
  children,
  onClick,
  disabled,
  tone = "brand",
}: {
  children: ReactNode;
  onClick: () => void;
  disabled?: boolean;
  tone?: "brand" | "rose";
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "text-xs font-medium hover:underline disabled:pointer-events-none disabled:opacity-50",
        tone === "rose" ? "text-rose-600 hover:text-rose-700" : "text-brand-600 hover:text-brand-700",
      )}
    >
      {children}
    </button>
  );
}

/** Secondary row actions stay out of the way until the row is hovered/focused. */
function HoverActions({ children }: { children: ReactNode }) {
  return (
    <div className="flex items-center gap-3 opacity-100 transition-opacity sm:opacity-0 sm:group-hover:opacity-100 sm:focus-within:opacity-100">
      {children}
    </div>
  );
}

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[5.5rem_1fr] gap-3 border-b border-slate-100 py-2 text-sm last:border-0 sm:grid-cols-[8rem_1fr]">
      <span className="text-xs text-slate-400">{label}</span>
      <span className="text-slate-800">{children}</span>
    </div>
  );
}

export default function AdminBusinessesPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const user = useAuth((state) => state.user);
  const [params, setParams] = useSearchParams();

  const status = params.get("status") ?? "";
  const trash = status === "trash";
  const qParam = params.get("q") ?? "";
  const categoryParam = params.get("category_id") ?? "";
  const ownerId = params.get("owner_id") ?? "";
  const ownerName = params.get("owner_name") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);

  const [search, setSearch] = useState(qParam);
  useEffect(() => setSearch(qParam), [qParam]);

  const query = new URLSearchParams({ page: String(page), per_page: "15" });
  if (trash) query.set("trash", "true");
  else if (status) query.set("status", status);
  if (qParam) query.set("q", qParam);
  if (categoryParam) query.set("category_id", categoryParam);
  if (ownerId) query.set("owner_id", ownerId);

  const businesses = useApiWithMeta<{ items: BusinessRow[] }, Meta>(
    ["admin", "businesses", status, qParam, categoryParam, ownerId, page],
    `/admin/businesses?${query.toString()}`,
  );
  const categories = useApi<{ items: CategoryRef[] }>(["categories"], "/categories");

  const items = businesses.data?.data.items ?? [];
  const meta = businesses.data?.meta;
  const loading = businesses.isLoading;

  const [detail, setDetail] = useState<BusinessRow | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editingBusiness, setEditingBusiness] = useState<AdminBusinessDetail | null>(null);
  const [confirmPermanent, setConfirmPermanent] = useState<BusinessRow | null>(null);

  function can(code: string): boolean {
    return user?.role === "superadmin" || Boolean(user?.permissions.includes(code));
  }

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["admin", "businesses"] });
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
    if (categoryParam) next.set("category_id", categoryParam);
    if (ownerId) next.set("owner_id", ownerId);
    if (ownerName) next.set("owner_name", ownerName);
    if (value) next.set("status", value);
    const suffix = next.toString();
    return `/admin/businesses${suffix ? `?${suffix}` : ""}`;
  }

  const approve = useMutation({
    mutationFn: (id: string) => api(`/admin/businesses/${id}/approve`, { method: "PATCH" }),
    onSuccess: async () => {
      toast("کسب‌وکار تأیید شد و پیام تأیید برای مالک ارسال شد.");
      await invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  const reject = useMutation({
    mutationFn: ({ id, reason }: { id: string; reason: string }) =>
      api(`/admin/businesses/${id}/reject`, {
        method: "PATCH",
        body: JSON.stringify({ reason }),
      }),
    onSuccess: async () => {
      toast("کسب‌وکار رد شد و پیام همراه با دلیل برای مالک ارسال شد.");
      await invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api(`/admin/businesses/${id}`, { method: "DELETE" }),
    onSuccess: async () => {
      toast("کسب‌وکار به سبد حذف‌شده‌ها منتقل شد.");
      await invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  const restore = useMutation({
    mutationFn: (id: string) => api(`/admin/businesses/${id}/restore`, { method: "POST" }),
    onSuccess: async () => {
      toast("کسب‌وکار بازیابی شد.");
      await invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  const purge = useMutation({
    mutationFn: (id: string) => api(`/admin/businesses/${id}/permanent`, { method: "DELETE" }),
    onSuccess: async () => {
      toast("کسب‌وکار به‌طور دائمی حذف شد.");
      setConfirmPermanent(null);
      await invalidate();
    },
    onError: (error: ApiError) => {
      setConfirmPermanent(null);
      if (error.code === "business_has_relations") {
        window.alert(`${error.message}\n\nپس از حذف این موارد، دوباره تلاش کنید.`);
      } else {
        toast(errorMessage(error));
      }
    },
  });

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) => {
      if (formMode === "create") {
        return api("/admin/businesses", { method: "POST", body: JSON.stringify(payload) });
      }
      return api(`/admin/businesses/${editingBusiness?.id}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: async () => {
      toast(formMode === "create" ? "کسب‌وکار ساخته شد." : "تغییرات ذخیره شد.");
      setFormMode(null);
      setEditingBusiness(null);
      await invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  function openCreate() {
    setEditingBusiness(null);
    setFormMode("create");
  }

  async function openEdit(business: BusinessRow) {
    try {
      const data = await api<AdminBusinessDetail>(`/admin/businesses/${business.id}`);
      setEditingBusiness(data);
      setFormMode("edit");
    } catch (error) {
      toast(errorMessage(error));
    }
  }

  function confirmReject(business: BusinessRow) {
    const reason = window.prompt("دلیل رد کسب‌وکار (برای مالک ارسال می‌شود):", "نقص مدارک");
    if (reason === null) return;
    const trimmed = reason.trim();
    if (!trimmed) {
      toast("دلیل رد کسب‌وکار را وارد کنید.");
      return;
    }
    reject.mutate({ id: business.id, reason: trimmed });
  }

  function confirmDelete(business: BusinessRow) {
    if (!window.confirm(`کسب‌وکار «${business.name}» به سبد حذف‌شده‌ها منتقل شود؟`)) return;
    remove.mutate(business.id);
  }

  const businessColumns: DataColumn<BusinessRow>[] = [
    {
      key: "business",
      header: "کسب‌وکار",
      cell: (business) => (
        <div className="flex items-start gap-3">
          <div className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-brand-50 text-xl md:h-12 md:w-12">
            {business.profile_image_url ? (
              <img
                src={business.profile_image_url}
                alt=""
                className="h-full w-full object-cover"
                loading="lazy"
              />
            ) : (
              <span aria-hidden>{business.category?.icon ?? "🏪"}</span>
            )}
          </div>
          <div className="min-w-0">
            <button
              type="button"
              onClick={() => setDetail(business)}
              className="block max-w-64 truncate text-right font-bold text-slate-900 transition-colors hover:text-brand-600"
            >
              {business.name}
            </button>
            <p className="mt-0.5 hidden text-[11px] text-slate-400 md:block" dir="ltr">
              {business.slug}
            </p>
            <p className="mt-1 hidden max-w-64 truncate text-xs text-slate-500 md:block">
              {business.address}
            </p>
          </div>
        </div>
      ),
    },
    {
      key: "category",
      header: "دسته",
      mobileHidden: true,
      cell: (business) => (
        <div className="text-xs text-slate-600">
          <p>{business.category?.name ?? "—"}</p>
          {business.subcategory && (
            <p className="mt-0.5 text-[11px] text-slate-400">{business.subcategory.name}</p>
          )}
        </div>
      ),
    },
    {
      key: "owner",
      header: "مالک",
      mobileHidden: true,
      cell: (business) => (
        <div className="text-xs text-slate-600">
          <p>{business.owner?.full_name || "بدون نام"}</p>
          {business.owner && (
            <p className="mt-0.5 text-[11px] text-slate-400" dir="ltr">
              {formatPhone(business.owner.phone)}
            </p>
          )}
        </div>
      ),
    },
    {
      key: "status",
      header: "وضعیت",
      cell: (business) => (
        <div>
          <StatusPill status={business.status} />
          <div className="mt-1.5 flex flex-wrap gap-1">
            {business.is_24h && (
              <span className="rounded bg-brand-50 px-1.5 py-0.5 text-[10px] text-brand-700">
                ۲۴ ساعته
              </span>
            )}
            {business.is_verified && (
              <span className="rounded bg-slate-100 px-1.5 py-0.5 text-[10px] text-slate-600">
                مجوز تأییدشده
              </span>
            )}
          </div>
        </div>
      ),
    },
    {
      key: "rating",
      header: "امتیاز",
      mobileHidden: true,
      cell: (business) => (
        <span className="text-xs text-slate-600">
          {formatRating(business.rating_avg)}
          <span className="mr-1 text-[11px] text-slate-400">({fa(business.rating_count)})</span>
        </span>
      ),
    },
    {
      key: "created",
      header: trash ? "حذف‌شده در" : "تاریخ ثبت",
      mobileHidden: true,
      cell: (business) => {
        const date = trash ? business.deleted_at : business.created_at;
        return (
          <span className="text-xs text-slate-500">{date ? formatJalali(date) : "—"}</span>
        );
      },
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-left",
      cell: (business) =>
        trash ? (
          <div className="flex flex-wrap items-center justify-end gap-3">
            <ActionButton
              disabled={restore.isPending}
              onClick={() => restore.mutate(business.id)}
            >
              بازیابی
            </ActionButton>
            <ActionButton tone="rose" onClick={() => setConfirmPermanent(business)}>
              حذف دائمی
            </ActionButton>
          </div>
        ) : (
          <div className="flex flex-wrap items-center justify-end gap-3">
            {business.status === "pending" && can("business.approve") && (
              <>
                <ActionButton
                  tone="green"
                  disabled={approve.isPending}
                  onClick={() => approve.mutate(business.id)}
                >
                  تأیید
                </ActionButton>
                <ActionButton
                  tone="rose"
                  disabled={reject.isPending}
                  onClick={() => confirmReject(business)}
                >
                  رد
                </ActionButton>
              </>
            )}
            <HoverActions>
              <RowLink onClick={() => setDetail(business)}>جزئیات</RowLink>
              {can("business.update") && (
                <span className="hidden md:inline">
                  <RowLink onClick={() => openEdit(business)}>ویرایش</RowLink>
                </span>
              )}
              {can("business.delete") && (
                <RowLink
                  tone="rose"
                  disabled={remove.isPending}
                  onClick={() => confirmDelete(business)}
                >
                  حذف
                </RowLink>
              )}
            </HoverActions>
            <Link
              to={`/admin/reviews?business_id=${business.id}&business_name=${encodeURIComponent(
                business.name,
              )}`}
              className="hidden rounded-lg border border-slate-200 bg-white px-2.5 py-1.5 text-xs font-medium text-slate-700 transition-colors hover:border-brand-300 hover:text-brand-700 md:inline-flex"
            >
              نمایش نظرات
            </Link>
          </div>
        ),
    },
  ];

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">فهرست کسب‌وکارها</h1>
          <p className="mt-1 text-xs text-slate-500">
            {meta ? `${fa(meta.total)} رکورد` : "در حال بارگذاری…"}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {can("business.create") && <Button size="sm" onClick={openCreate}>افزودن کسب‌وکار</Button>}
          <Button
            size="sm"
            variant="outline"
            onClick={() => void businesses.refetch()}
            disabled={loading}
          >
            به‌روزرسانی
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        {FILTERS.map((filter) => (
          <Link
            key={filter.value || "all"}
            to={filterHref(filter.value)}
            className={cn(
              "rounded-full border px-3 py-1.5 text-xs transition-colors",
              status === filter.value
                ? "border-brand-600 bg-brand-600 text-white"
                : "border-slate-200 bg-white text-slate-600 hover:border-brand-300",
            )}
          >
            {filter.label}
          </Link>
        ))}
      </div>

      {ownerId && (
        <div className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-brand-100 bg-brand-50/60 px-3 py-2 text-xs text-brand-800">
          <span>
            فقط کسب‌وکارهای{" "}
            <b className="font-bold">{ownerName || "کاربر انتخاب‌شده"}</b>
          </span>
          <Link
            to={`/admin/businesses${status ? `?status=${status}` : ""}`}
            className="font-medium text-brand-700 hover:underline"
          >
            حذف فیلتر مالک
          </Link>
        </div>
      )}

      <DataTable
        columns={businessColumns}
        rows={items}
        rowKey={(business) => business.id}
        loading={loading}
        error={businesses.error ? errorMessage(businesses.error) : null}
        empty={trash ? "سبد حذف‌شده‌ها خالی است." : "کسب‌وکاری با این فیلتر پیدا نشد."}
        minWidthClassName="min-w-[980px]"
        meta={
          meta
            ? { page: meta.page, pages: meta.pages, total: meta.total }
            : undefined
        }
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
                placeholder="جستجوی نام یا شناسه…"
                aria-label="جستجوی کسب‌وکار"
              />
              <Button size="sm" type="submit" variant="outline">
                جستجو
              </Button>
            </form>
            <select
              value={categoryParam}
              onChange={(event) =>
                updateParams({ category_id: event.target.value || null, page: null })
              }
              className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
              aria-label="فیلتر دسته"
            >
              <option value="">همه دسته‌ها</option>
              {categories.data?.items.map((category) => (
                <option key={category.id} value={category.id}>
                  {category.name}
                </option>
              ))}
            </select>
          </div>
        }
      />

      {detail && (
        <AdminModal title={`جزئیات ${detail.name}`} onClose={() => setDetail(null)}>
          <div className="mb-4 flex items-start gap-4 rounded-xl border border-slate-100 bg-slate-50/60 p-3">
            <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-brand-50 text-3xl">
              {detail.profile_image_url ? (
                <img
                  src={detail.profile_image_url}
                  alt=""
                  className="h-full w-full object-cover"
                />
              ) : (
                <span aria-hidden>{detail.category?.icon ?? "🏪"}</span>
              )}
            </div>
            <div className="min-w-0">
              <p className="font-bold text-slate-900">{detail.name}</p>
              <p className="mt-0.5 text-[11px] text-slate-400" dir="ltr">
                {detail.slug}
              </p>
              <div className="mt-2 flex flex-wrap items-center gap-3 text-xs">
                {!trash && (
                  <Link
                    to={`/businesses/${detail.slug}`}
                    target="_blank"
                    rel="noreferrer"
                    className="font-medium text-brand-600 hover:underline"
                  >
                    مشاهده صفحه عمومی
                  </Link>
                )}
                <Link
                  to={`/admin/reviews?business_id=${detail.id}&business_name=${encodeURIComponent(
                    detail.name,
                  )}`}
                  className="font-medium text-brand-600 hover:underline"
                >
                  نمایش نظرات
                </Link>
                {!trash && can("business.update") && (
                  <button
                    type="button"
                    onClick={() => {
                      setDetail(null);
                      openEdit(detail);
                    }}
                    className="font-medium text-brand-600 hover:underline"
                  >
                    ویرایش
                  </button>
                )}
              </div>
            </div>
          </div>
          <div className="space-y-1">
            <DetailRow label="شناسه">{detail.slug}</DetailRow>
            <DetailRow label="وضعیت">
              <StatusPill status={detail.status} />
            </DetailRow>
            <DetailRow label="دسته‌بندی">
              {detail.category?.name ?? "—"}
              {detail.subcategory ? ` / ${detail.subcategory.name}` : ""}
            </DetailRow>
            <DetailRow label="مالک">
              {detail.owner?.full_name || "بدون نام"} —{" "}
              <span dir="ltr">{detail.owner ? formatPhone(detail.owner.phone) : "—"}</span>
            </DetailRow>
            <DetailRow label="آدرس">{detail.address}</DetailRow>
            <DetailRow label="تلفن">{detail.phone_business || "—"}</DetailRow>
            <DetailRow label="توضیح کوتاه">{detail.short_description || "—"}</DetailRow>
            <DetailRow label="توضیحات">{detail.description || "—"}</DetailRow>
            <DetailRow label="اینستاگرام">{detail.instagram || "—"}</DetailRow>
            <DetailRow label="مختصات">
              {detail.geo ? `${detail.geo.lat}, ${detail.geo.lng}` : "—"}
            </DetailRow>
            <DetailRow label="امتیاز">
              {formatRating(detail.rating_avg)} ({fa(detail.rating_count)} نظر)
            </DetailRow>
            <DetailRow label="۲۴ ساعته">{detail.is_24h ? "بله" : "خیر"}</DetailRow>
            <DetailRow label="مجوز">{detail.is_verified ? "تأییدشده" : "تأییدنشده"}</DetailRow>
            <DetailRow label="دلیل رد">{detail.rejection_reason || "—"}</DetailRow>
            <DetailRow label="ثبت">
              {detail.created_at ? formatJalali(detail.created_at) : "—"}
            </DetailRow>
          </div>
        </AdminModal>
      )}

      {formMode && (
        <AdminBusinessWizard
          business={formMode === "edit" ? editingBusiness : null}
          saving={save.isPending}
          onClose={() => {
            setFormMode(null);
            setEditingBusiness(null);
          }}
          onSubmit={(payload) => save.mutate(payload)}
        />
      )}

      <ConfirmSheet
        open={confirmPermanent !== null}
        title="حذف دائمی کسب‌وکار"
        description={
          <>
            کسب‌وکار{" "}
            <span className="font-bold text-slate-800">{confirmPermanent?.name}</span> به‌طور
            کامل از پایگاه داده حذف شود؟ اگر این کسب‌وکار نظر، پیشنهاد قیمت یا مجوز
            داشته باشد، ابتدا باید آن‌ها را حذف کنید. این عملیات بازگشت‌ناپذیر است.
          </>
        }
        confirmLabel="حذف دائمی"
        tone="rose"
        loading={purge.isPending}
        onClose={() => setConfirmPermanent(null)}
        onConfirm={() => confirmPermanent && purge.mutate(confirmPermanent.id)}
      />
    </div>
  );
}
