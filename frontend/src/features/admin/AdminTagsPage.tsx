import { useEffect, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useSearchParams } from "react-router-dom";

import { Button, Spinner } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { useApi, useApiWithMeta } from "@/lib/query";
import { MAX_VISIBLE_TAGS } from "@/features/business/create/types";
import { AdminModal } from "@/features/admin/AdminModal";
import { DataTable, type DataColumn, type PageMeta } from "@/features/admin/data-table";

interface TagRow {
  id: number;
  name: string;
  status: string;
  is_custom: boolean;
  usage_count: number;
}

interface SubcategoryRow {
  id: number;
  category_id: number;
  name: string;
  slug: string;
  icon: string;
  standard_tags: string[];
  visible_tags: string[] | null;
}

interface CategoryRow {
  id: number;
  name: string;
  icon: string;
  subcategories: SubcategoryRow[];
}

interface SubcategoryOption extends SubcategoryRow {
  category_name: string;
  category_icon: string;
}

const FILTERS = [
  { label: "همه", value: "" },
  { label: "تأییدشده", value: "approved" },
  { label: "در انتظار", value: "pending" },
  { label: "ردشده", value: "rejected" },
];

const EMPTY = { name: "", status: "approved", is_custom: true };

/** Mirrors the backend fallback: an unset subset shows the first few tags. */
function visibleTagsOf(subcategory: SubcategoryRow): string[] {
  return subcategory.visible_tags ?? subcategory.standard_tags.slice(0, MAX_VISIBLE_TAGS);
}

function parseTags(value: string): string[] {
  return Array.from(
    new Set(
      value
        .split(/[,،\n]/)
        .map((tag) => tag.trim())
        .filter(Boolean),
    ),
  );
}

export default function AdminTagsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();

  const subcategoryId = params.get("subcategory_id") ?? "";
  const status = params.get("status") ?? "";
  const qParam = params.get("q") ?? "";
  const page = Math.max(1, Number(params.get("page") ?? "1") || 1);

  const [search, setSearch] = useState(qParam);
  useEffect(() => setSearch(qParam), [qParam]);

  const [mode, setMode] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<TagRow | null>(null);
  const [form, setForm] = useState(EMPTY);
  const [bulk, setBulk] = useState("");

  const categories = useApi<{ items: CategoryRow[] }>(
    ["admin", "categories"],
    "/admin/categories",
  );
  const subcategories: SubcategoryOption[] = (categories.data?.items ?? []).flatMap(
    (category) =>
      category.subcategories.map((sub) => ({
        ...sub,
        category_name: category.name,
        category_icon: category.icon,
      })),
  );
  const selected =
    subcategories.find((item) => String(item.id) === subcategoryId) ?? null;

  const query = new URLSearchParams({ page: String(page), per_page: "20" });
  if (status) query.set("status", status);
  if (qParam) query.set("q", qParam);

  const tags = useApiWithMeta<{ items: TagRow[] }, PageMeta>(
    ["admin", "tags", status, qParam, page],
    `/admin/tags?${query.toString()}`,
    { enabled: !subcategoryId },
  );

  const items = tags.data?.data.items ?? [];
  const meta = tags.data?.meta;

  useEffect(() => {
    const timer = setTimeout(() => {
      const next = search.trim();
      if (next === qParam) return;
      const params = new URLSearchParams(window.location.search);
      if (next) params.set("q", next);
      else params.delete("q");
      params.delete("page");
      setParams(params);
    }, 300);
    return () => clearTimeout(timer);
  }, [search, qParam, setParams]);

  function updateParams(patch: Record<string, string | null>) {
    const next = new URLSearchParams(params);
    for (const [key, value] of Object.entries(patch)) {
      if (value === null || value === "") next.delete(key);
      else next.set(key, value);
    }
    setParams(next);
  }

  function invalidateTags() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
  }

  function invalidateCatalog() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "categories"] });
    void queryClient.invalidateQueries({ queryKey: ["categories"] });
  }

  const save = useMutation({
    mutationFn: () =>
      mode === "create"
        ? api("/admin/tags", { method: "POST", body: JSON.stringify(form) })
        : api(`/admin/tags/${editing?.id}`, { method: "PATCH", body: JSON.stringify(form) }),
    onSuccess: () => {
      toast(mode === "create" ? "برچسب ساخته شد." : "برچسب ذخیره شد.");
      setMode(null);
      setEditing(null);
      invalidateTags();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api(`/admin/tags/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast("برچسب حذف شد.");
      invalidateTags();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const updateSubcategory = useMutation({
    mutationFn: ({
      id,
      body,
    }: {
      id: number;
      body: Record<string, unknown>;
      message: string;
    }) =>
      api(`/admin/subcategories/${id}`, {
        method: "PATCH",
        body: JSON.stringify(body),
      }),
    onSuccess: (_data, variables) => {
      toast(variables.message);
      invalidateCatalog();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  function addBulkTags(event: FormEvent) {
    event.preventDefault();
    if (!selected) return;
    const names = parseTags(bulk);
    if (names.length === 0) {
      toast("برچسبی برای افزودن وارد نشده است.");
      return;
    }
    const standard = Array.from(new Set([...selected.standard_tags, ...names]));
    updateSubcategory.mutate({
      id: selected.id,
      body: { standard_tags: standard },
      message: `${names.length} برچسب اضافه شد.`,
    });
    setBulk("");
  }

  function toggleVisible(tag: string) {
    if (!selected) return;
    const current = visibleTagsOf(selected);
    const next = current.includes(tag)
      ? current.filter((item) => item !== tag)
      : [...current, tag];
    if (next.length > MAX_VISIBLE_TAGS) {
      toast(`حداکثر ${MAX_VISIBLE_TAGS} برچسب می‌تواند به کاربر نمایش داده شود.`);
      return;
    }
    updateSubcategory.mutate({
      id: selected.id,
      body: { visible_tags: next },
      message: "تنظیم نمایش برچسب ذخیره شد.",
    });
  }

  function removeSubcategoryTag(tag: string) {
    if (!selected) return;
    updateSubcategory.mutate({
      id: selected.id,
      body: {
        standard_tags: selected.standard_tags.filter((item) => item !== tag),
        visible_tags: visibleTagsOf(selected).filter((item) => item !== tag),
      },
      message: "برچسب حذف شد.",
    });
  }

  const columns: DataColumn<TagRow>[] = [
    {
      key: "name",
      header: "برچسب",
      cell: (row) => <span className="font-bold text-slate-900">{row.name}</span>,
    },
    {
      key: "status",
      header: "وضعیت",
      cell: (row) => (
        <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
          {row.status === "approved" ? "تأییدشده" : row.status === "pending" ? "در انتظار" : "ردشده"}
        </span>
      ),
    },
    {
      key: "custom",
      header: "نوع",
      cell: (row) => <span className="text-xs text-slate-500">{row.is_custom ? "کاربر" : "سیستمی"}</span>,
    },
    {
      key: "usage",
      header: "استفاده",
      cell: (row) => <span className="text-xs text-slate-600">{row.usage_count}</span>,
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-left",
      cell: (row) => (
        <div className="flex justify-end gap-1">
          <Button
            size="sm"
            onClick={() => {
              setEditing(row);
              setForm({ name: row.name, status: row.status, is_custom: row.is_custom });
              setMode("edit");
            }}
          >
            ویرایش
          </Button>
          <Button
            size="sm"
            variant="danger"
            onClick={() => {
              if (!window.confirm(`برچسب «${row.name}» حذف شود؟`)) return;
              remove.mutate(row.id);
            }}
          >
            حذف
          </Button>
        </div>
      ),
    },
  ];

  if (subcategoryId && categories.isLoading) {
    return (
      <div className="flex justify-center py-12 text-brand-600">
        <Spinner />
      </div>
    );
  }
  if (subcategoryId && !selected) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-600">
        زیردسته انتخاب‌شده پیدا نشد.{" "}
        <Link to="/admin/tags" className="font-medium text-brand-700 hover:underline">
          بازگشت به فهرست برچسب‌ها
        </Link>
      </div>
    );
  }

  const visibleTags = selected ? visibleTagsOf(selected) : [];
  const subcategoryColumns: DataColumn<string>[] = [    {
      key: "name",
      header: "برچسب",
      cell: (tag) => <span className="font-bold text-slate-900">{tag}</span>,
    },
    {
      key: "visibility",
      header: "نمایش در فرم",
      cell: (tag) => (
        <span
          className={
            visibleTags.includes(tag)
              ? "rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700"
              : "rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500"
          }
        >
          {visibleTags.includes(tag) ? "نمایش به کاربر" : "فقط جستجو"}
        </span>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-left",
      cell: (tag) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" variant="outline" onClick={() => toggleVisible(tag)}>
            {visibleTags.includes(tag) ? "پنهان کردن" : "نمایش دادن"}
          </Button>
          <Button
            size="sm"
            variant="danger"
            onClick={() => {
              if (!window.confirm(`برچسب «${tag}» از این زیردسته حذف شود؟`)) return;
              removeSubcategoryTag(tag);
            }}
          >
            حذف
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">برچسب‌ها</h1>
          <p className="mt-1 text-xs text-slate-500">
            {selected
              ? `برچسب‌های ${selected.icon} ${selected.name} — ${selected.category_name}`
              : "برچسب‌های خدمت و برچسب‌های سفارشی کسب‌وکارها"}
          </p>
        </div>
        {!selected && (
          <Button
            onClick={() => {
              setForm(EMPTY);
              setEditing(null);
              setMode("create");
            }}
          >
            افزودن برچسب
          </Button>
        )}
      </div>

      <div className="flex flex-wrap items-center gap-2 rounded-2xl border border-slate-200 bg-white p-2.5">
        <span className="text-xs text-slate-500">زیردسته:</span>
        <select
          value={subcategoryId}
          onChange={(event) =>
            updateParams({
              subcategory_id: event.target.value || null,
              page: null,
            })
          }
          className="h-10 min-w-[220px] flex-1 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"
          aria-label="انتخاب زیردسته"
        >
          <option value="">همه برچسب‌ها (کسب‌وکارها)</option>
          {(categories.data?.items ?? []).map((category) => (
            <optgroup key={category.id} label={`${category.icon} ${category.name}`}>
              {category.subcategories.map((sub) => (
                <option key={sub.id} value={sub.id}>
                  {sub.icon} {sub.name}
                </option>
              ))}
            </optgroup>
          ))}
        </select>
        <Link
          to="/admin/categories"
          className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-xs text-slate-600 hover:border-brand-300 hover:text-brand-700"
        >
          مدیریت دسته‌بندی‌ها
        </Link>
      </div>

      {selected ? (
        <>
          <div className="grid gap-2 sm:grid-cols-3">
            <div className="rounded-2xl border border-slate-200 bg-white p-3">
              <p className="text-[11px] text-slate-400">کل برچسب‌ها</p>
              <p className="mt-1 text-lg font-black text-slate-900">
                {selected.standard_tags.length}
              </p>
            </div>
            <div className="rounded-2xl border border-emerald-100 bg-emerald-50/60 p-3">
              <p className="text-[11px] text-emerald-700">نمایش به کاربر</p>
              <p className="mt-1 text-lg font-black text-emerald-800">
                {visibleTags.length} از {MAX_VISIBLE_TAGS}
              </p>
            </div>
            <div className="rounded-2xl border border-slate-200 bg-white p-3">
              <p className="text-[11px] text-slate-400">فقط جستجو</p>
              <p className="mt-1 text-lg font-black text-slate-900">
                {Math.max(0, selected.standard_tags.length - visibleTags.length)}
              </p>
            </div>
          </div>

          <form
            onSubmit={addBulkTags}
            className="flex flex-col gap-2 rounded-2xl border border-slate-200 bg-white p-3 sm:flex-row"
          >
            <Input
              value={bulk}
              onChange={(event) => setBulk(event.target.value)}
              placeholder="برچسب‌ها را با کاما جدا کنید: تعمیر یخچال، تعمیر لباسشویی"
              aria-label="افزودن گروهی برچسب"
            />
            <Button type="submit" loading={updateSubcategory.isPending} className="shrink-0">
              افزودن گروهی
            </Button>
          </form>
          <p className="-mt-1 text-[11px] leading-5 text-slate-500">
            برچسب‌های جدید ابتدا فقط برای جستجو ثبت می‌شوند. حداکثر{" "}
            {MAX_VISIBLE_TAGS} برچسب را می‌توانید برای نمایش در فرم افزودن کسب‌وکار انتخاب
            کنید؛ بقیه به‌صورت خودکار به کسب‌وکارها وصل می‌شوند و فقط در جستجو استفاده
            می‌شوند.
          </p>

          <DataTable
            columns={subcategoryColumns}
            rows={selected.standard_tags}
            rowKey={(tag) => tag}
            loading={categories.isLoading}
            error={categories.error ? errorMessage(categories.error) : null}
            empty="برای این زیردسته برچسبی ثبت نشده است."
            minWidthClassName="min-w-[640px]"
          />
        </>
      ) : (
        <>
          <div className="flex flex-wrap gap-2">
            {FILTERS.map((item) => (
              <button
                key={item.value || "all"}
                type="button"
                onClick={() => updateParams({ status: item.value || null, page: null })}
                className={
                  status === item.value
                    ? "rounded-full bg-brand-600 px-3 py-1 text-xs text-white"
                    : "rounded-full border border-slate-200 bg-white px-3 py-1 text-xs text-slate-600"
                }
              >
                {item.label}
              </button>
            ))}
          </div>

          <DataTable
            columns={columns}
            rows={items}
            rowKey={(row) => row.id}
            loading={tags.isLoading}
            error={tags.error ? errorMessage(tags.error) : null}
            empty="برچسبی پیدا نشد."
            minWidthClassName="min-w-[700px]"
            meta={meta ? { page: meta.page, pages: meta.pages, total: meta.total } : undefined}
            onPageChange={(nextPage) => updateParams({ page: String(nextPage) })}
            toolbar={
              <Input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="جستجوی برچسب…"
                aria-label="جستجوی برچسب"
              />
            }
          />
        </>
      )}

      {mode && (
        <AdminModal title={mode === "create" ? "افزودن برچسب" : "ویرایش برچسب"} onClose={() => setMode(null)}>
          <form onSubmit={submit} className="space-y-3">
            <label className="space-y-1 text-xs text-slate-500">
              نام
              <Input
                required
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </label>
            <label className="space-y-1 text-xs text-slate-500">
              وضعیت
              <select
                value={form.status}
                onChange={(event) => setForm({ ...form, status: event.target.value })}
                className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"
              >
                <option value="approved">تأییدشده</option>
                <option value="pending">در انتظار</option>
                <option value="rejected">ردشده</option>
              </select>
            </label>
            <label className="flex items-center gap-2 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.is_custom}
                onChange={(event) => setForm({ ...form, is_custom: event.target.checked })}
              />
              برچسب سفارشی
            </label>
            <div className="flex gap-2">
              <Button type="submit" loading={save.isPending}>
                ذخیره
              </Button>
              <Button type="button" variant="ghost" onClick={() => setMode(null)}>
                انصراف
              </Button>
            </div>
          </form>
        </AdminModal>
      )}
    </div>
  );
}
