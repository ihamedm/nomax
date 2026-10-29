import { useEffect, useState, type FormEvent, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fa, formatPhone, formatRating } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";
import { useApi, useApiWithMeta } from "@/lib/query";
import { useAuth } from "@/stores/auth";
import { AdminModal } from "@/features/admin/AdminModal";
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
  rejection_reason?: string | null;
  owner: Owner | null;
  created_at?: string | null;
  updated_at?: string | null;
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
];

const STATUS_META: Record<BusinessStatus, { label: string; className: string }> = {
  pending: { label: "در انتظار", className: "bg-amber-50 text-amber-700" },
  approved: { label: "تأییدشده", className: "bg-emerald-50 text-emerald-700" },
  rejected: { label: "ردشده", className: "bg-rose-50 text-rose-700" },
};

const EMPTY_FORM = {
  name: "",
  category_id: "",
  address: "",
  owner_phone: "",
  short_description: "",
  description: "",
  phone_business: "",
  is_24h: false,
  is_verified: false,
  status: "pending" as BusinessStatus,
};

type BusinessForm = typeof EMPTY_FORM;

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

function DetailRow({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div className="grid grid-cols-[8rem_1fr] gap-3 border-b border-slate-100 py-2 text-sm last:border-0">
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
  const qParam = params.get("q") ?? "";
  const categoryParam = params.get("category_id") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);

  const [search, setSearch] = useState(qParam);
  useEffect(() => setSearch(qParam), [qParam]);

  const query = new URLSearchParams({ page: String(page), per_page: "15" });
  if (status) query.set("status", status);
  if (qParam) query.set("q", qParam);
  if (categoryParam) query.set("category_id", categoryParam);

  const businesses = useApiWithMeta<{ items: BusinessRow[] }, Meta>(
    ["admin", "businesses", status, qParam, categoryParam, page],
    `/admin/businesses?${query.toString()}`,
  );
  const categories = useApi<{ items: CategoryRef[] }>(["categories"], "/categories");

  const items = businesses.data?.data.items ?? [];
  const meta = businesses.data?.meta;
  const loading = businesses.isLoading;

  const [detail, setDetail] = useState<BusinessRow | null>(null);
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [form, setForm] = useState<BusinessForm>(EMPTY_FORM);

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
      toast("کسب‌وکار حذف شد.");
      await invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  const save = useMutation({
    mutationFn: (payload: Record<string, unknown>) => {
      if (formMode === "create") {
        return api("/admin/businesses", { method: "POST", body: JSON.stringify(payload) });
      }
      return api(`/admin/businesses/${editingId}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: async () => {
      toast(formMode === "create" ? "کسب‌وکار ساخته شد." : "تغییرات ذخیره شد.");
      setFormMode(null);
      setEditingId(null);
      await invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  function openCreate() {
    setForm(EMPTY_FORM);
    setEditingId(null);
    setFormMode("create");
  }

  function openEdit(business: BusinessRow) {
    setForm({
      name: business.name,
      category_id: business.category ? String(business.category.id) : "",
      address: business.address,
      owner_phone: business.owner?.phone ?? "",
      short_description: business.short_description ?? "",
      description: business.description ?? "",
      phone_business: business.phone_business ?? "",
      is_24h: business.is_24h,
      is_verified: business.is_verified,
      status: business.status,
    });
    setEditingId(business.id);
    setFormMode("edit");
  }

  function submitForm(event: FormEvent) {
    event.preventDefault();
    const payload: Record<string, unknown> = {
      name: form.name.trim(),
      category_id: Number(form.category_id),
      address: form.address.trim(),
      short_description: form.short_description.trim(),
      description: form.description.trim() || null,
      phone_business: form.phone_business.trim() || null,
      is_24h: form.is_24h,
      is_verified: form.is_verified,
      status: form.status,
    };
    if (formMode === "create") payload.owner_phone = form.owner_phone.trim();
    save.mutate(payload);
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
    if (!window.confirm(`کسب‌وکار «${business.name}» حذف شود؟`)) return;
    remove.mutate(business.id);
  }

  const businessColumns: DataColumn<BusinessRow>[] = [
    {
      key: "business",
      header: "کسب‌وکار",
      cell: (business) => (
        <div>
          <p className="font-bold text-slate-900">{business.name}</p>
          <p className="mt-0.5 text-[11px] text-slate-400" dir="ltr">
            {business.slug}
          </p>
          <p className="mt-1 max-w-64 truncate text-xs text-slate-500">{business.address}</p>
        </div>
      ),
    },
    {
      key: "category",
      header: "دسته",
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
      cell: (business) => (
        <span className="text-xs text-slate-600">
          {formatRating(business.rating_avg)}
          <span className="mr-1 text-[11px] text-slate-400">({fa(business.rating_count)})</span>
        </span>
      ),
    },
    {
      key: "created",
      header: "تاریخ ثبت",
      cell: (business) => (
        <span className="text-xs text-slate-500">
          {business.created_at ? formatJalali(business.created_at) : "—"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-left",
      cell: (business) => (
        <div className="flex flex-wrap justify-end gap-1">
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
          <ActionButton onClick={() => setDetail(business)}>جزئیات</ActionButton>
          {can("business.update") && (
            <ActionButton tone="brand" onClick={() => openEdit(business)}>
              ویرایش
            </ActionButton>
          )}
          {can("business.delete") && (
            <ActionButton
              disabled={remove.isPending}
              onClick={() => confirmDelete(business)}
            >
              حذف
            </ActionButton>
          )}
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

      <DataTable
        columns={businessColumns}
        rows={items}
        rowKey={(business) => business.id}
        loading={loading}
        error={businesses.error ? errorMessage(businesses.error) : null}
        empty="کسب‌وکاری با این فیلتر پیدا نشد."
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
        <AdminModal
          title={formMode === "create" ? "افزودن کسب‌وکار" : "ویرایش کسب‌وکار"}
          onClose={() => {
            setFormMode(null);
            setEditingId(null);
          }}
        >
          <form onSubmit={submitForm} className="space-y-4">
            <div className="grid gap-3 sm:grid-cols-2">
              <label className="space-y-1 text-xs text-slate-500">
                نام
                <Input
                  required
                  value={form.name}
                  onChange={(event) => setForm({ ...form, name: event.target.value })}
                />
              </label>
              <label className="space-y-1 text-xs text-slate-500">
                دسته‌بندی
                <select
                  required
                  value={form.category_id}
                  onChange={(event) => setForm({ ...form, category_id: event.target.value })}
                  className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"
                >
                  <option value="">انتخاب دسته…</option>
                  {categories.data?.items.map((category) => (
                    <option key={category.id} value={category.id}>
                      {category.name}
                    </option>
                  ))}
                </select>
              </label>
              {formMode === "create" && (
                <label className="space-y-1 text-xs text-slate-500">
                  موبایل مالک
                  <Input
                    required
                    dir="ltr"
                    placeholder="0912 345 6789"
                    value={form.owner_phone}
                    onChange={(event) => setForm({ ...form, owner_phone: event.target.value })}
                  />
                </label>
              )}
              <label className="space-y-1 text-xs text-slate-500">
                وضعیت
                <select
                  value={form.status}
                  onChange={(event) =>
                    setForm({ ...form, status: event.target.value as BusinessStatus })
                  }
                  className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"
                >
                  <option value="pending">در انتظار</option>
                  <option value="approved">تأییدشده</option>
                  <option value="rejected">ردشده</option>
                </select>
              </label>
              <label className="space-y-1 text-xs text-slate-500 sm:col-span-2">
                آدرس
                <Input
                  required
                  value={form.address}
                  onChange={(event) => setForm({ ...form, address: event.target.value })}
                />
              </label>
              <label className="space-y-1 text-xs text-slate-500">
                تلفن کسب‌وکار
                <Input
                  dir="ltr"
                  value={form.phone_business}
                  onChange={(event) => setForm({ ...form, phone_business: event.target.value })}
                />
              </label>
              <label className="space-y-1 text-xs text-slate-500">
                توضیح کوتاه
                <Input
                  value={form.short_description}
                  onChange={(event) => setForm({ ...form, short_description: event.target.value })}
                />
              </label>
              <label className="space-y-1 text-xs text-slate-500 sm:col-span-2">
                توضیحات
                <textarea
                  value={form.description}
                  onChange={(event) => setForm({ ...form, description: event.target.value })}
                  className="min-h-24 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                />
              </label>
            </div>
            <div className="flex flex-wrap gap-4 text-sm text-slate-700">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_24h}
                  onChange={(event) => setForm({ ...form, is_24h: event.target.checked })}
                />
                ۲۴ ساعته
              </label>
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={form.is_verified}
                  onChange={(event) => setForm({ ...form, is_verified: event.target.checked })}
                />
                مجوز تأییدشده
              </label>
            </div>
            <div className="flex gap-2">
              <Button type="submit" loading={save.isPending}>
                {formMode === "create" ? "ساخت کسب‌وکار" : "ذخیره تغییرات"}
              </Button>
              <Button
                type="button"
                variant="ghost"
                onClick={() => {
                  setFormMode(null);
                  setEditingId(null);
                }}
              >
                انصراف
              </Button>
            </div>
          </form>
        </AdminModal>
      )}
    </div>
  );
}
