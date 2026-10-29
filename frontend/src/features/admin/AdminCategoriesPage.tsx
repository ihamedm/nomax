import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { useApi } from "@/lib/query";
import { AdminModal } from "@/features/admin/AdminModal";
import { DataTable, type DataColumn } from "@/features/admin/data-table";

interface SubcategoryRow {
  id: number;
  category_id: number;
  name: string;
  slug: string;
  icon: string;
  sort_order: number;
}

interface CategoryRow {
  id: number;
  name: string;
  slug: string;
  icon: string;
  sort_order: number;
  is_active: boolean;
  subcategories: SubcategoryRow[];
}

const EMPTY_CATEGORY = { name: "", slug: "", icon: "❓", sort_order: 0, is_active: true };

export default function AdminCategoriesPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useApi<{ items: CategoryRow[] }>(
    ["admin", "categories"],
    "/admin/categories",
  );
  const [search, setSearch] = useState("");
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<CategoryRow | null>(null);
  const [form, setForm] = useState(EMPTY_CATEGORY);
  const [subCategory, setSubCategory] = useState<CategoryRow | null>(null);
  const [subEditingId, setSubEditingId] = useState<number | null>(null);
  const [subForm, setSubForm] = useState({ name: "", slug: "", icon: "❓", sort_order: 0 });

  const items = data?.items ?? [];
  const filtered = items.filter(
    (item) =>
      !search.trim() ||
      item.name.includes(search.trim()) ||
      item.slug.includes(search.trim()),
  );

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "categories"] });
    void queryClient.invalidateQueries({ queryKey: ["categories"] });
  }

  const saveCategory = useMutation({
    mutationFn: () =>
      formMode === "create"
        ? api("/admin/categories", { method: "POST", body: JSON.stringify(form) })
        : api(`/admin/categories/${editing?.id}`, {
            method: "PATCH",
            body: JSON.stringify(form),
          }),
    onSuccess: () => {
      toast(formMode === "create" ? "دسته ساخته شد." : "دسته ذخیره شد.");
      setFormMode(null);
      setEditing(null);
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const deleteCategory = useMutation({
    mutationFn: (id: number) => api(`/admin/categories/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast("دسته حذف شد.");
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const saveSub = useMutation({
    mutationFn: () =>
      subEditingId
        ? api(`/admin/subcategories/${subEditingId}`, {
            method: "PATCH",
            body: JSON.stringify(subForm),
          })
        : api("/admin/subcategories", {
            method: "POST",
            body: JSON.stringify({ ...subForm, category_id: subCategory?.id }),
          }),
    onSuccess: async () => {
      toast(subEditingId ? "زیردسته ذخیره شد." : "زیردسته ساخته شد.");
      setSubEditingId(null);
      setSubForm({ name: "", slug: "", icon: "❓", sort_order: 0 });
      invalidate();
      if (subCategory) {
        const refreshed = await queryClient.fetchQuery<{ items: CategoryRow[] }>({
          queryKey: ["admin", "categories"],
          queryFn: () => api<{ items: CategoryRow[] }>("/admin/categories"),
        });
        const current = refreshed.items.find((item) => item.id === subCategory.id);
        if (current) setSubCategory(current);
      }
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const deleteSub = useMutation({
    mutationFn: (id: number) => api(`/admin/subcategories/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast("زیردسته حذف شد.");
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  function openCreate() {
    setForm(EMPTY_CATEGORY);
    setEditing(null);
    setFormMode("create");
  }

  function openEdit(category: CategoryRow) {
    setForm({
      name: category.name,
      slug: category.slug,
      icon: category.icon,
      sort_order: category.sort_order,
      is_active: category.is_active,
    });
    setEditing(category);
    setFormMode("edit");
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    saveCategory.mutate();
  }

  const columns: DataColumn<CategoryRow>[] = [
    {
      key: "name",
      header: "دسته‌بندی",
      cell: (row) => (
        <div>
          <p className="font-bold text-slate-900">
            <span className="ml-1">{row.icon}</span>
            {row.name}
          </p>
          <p className="mt-0.5 text-[11px] text-slate-400" dir="ltr">
            {row.slug}
          </p>
        </div>
      ),
    },
    {
      key: "subs",
      header: "زیردسته‌ها",
      cell: (row) => <span className="text-xs text-slate-600">{row.subcategories.length}</span>,
    },
    {
      key: "sort",
      header: "ترتیب",
      cell: (row) => <span className="text-xs text-slate-500">{row.sort_order}</span>,
    },
    {
      key: "active",
      header: "وضعیت",
      cell: (row) => (
        <span
          className={
            row.is_active
              ? "rounded-full bg-emerald-50 px-2 py-0.5 text-[11px] text-emerald-700"
              : "rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-500"
          }
        >
          {row.is_active ? "فعال" : "غیرفعال"}
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
            variant="outline"
            onClick={() => {
              setSubCategory(row);
              setSubEditingId(null);
              setSubForm({ name: "", slug: "", icon: "❓", sort_order: 0 });
            }}
          >
            زیردسته‌ها
          </Button>
          <Button size="sm" onClick={() => openEdit(row)}>
            ویرایش
          </Button>
          <Button
            size="sm"
            variant="danger"
            disabled={deleteCategory.isPending}
            onClick={() => {
              if (!window.confirm(`دسته «${row.name}» و زیردسته‌هایش حذف شوند؟`)) return;
              deleteCategory.mutate(row.id);
            }}
          >
            حذف
          </Button>
        </div>
      ),
    },
  ];

  const subColumns: DataColumn<SubcategoryRow>[] = [
    {
      key: "name",
      header: "زیردسته",
      cell: (row) => (
        <span className="text-sm text-slate-800">
          {row.icon} {row.name}
        </span>
      ),
    },
    {
      key: "slug",
      header: "شناسه",
      cell: (row) => (
        <span className="text-xs text-slate-400" dir="ltr">
          {row.slug}
        </span>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-left",
      cell: (row) => (
        <div className="flex justify-end gap-1">
          <Button
            size="sm"
            variant="outline"
            onClick={() => {
              setSubEditingId(row.id);
              setSubForm({
                name: row.name,
                slug: row.slug,
                icon: row.icon,
                sort_order: row.sort_order,
              });
            }}
          >
            ویرایش
          </Button>
          <Button
            size="sm"
            variant="danger"
            onClick={() => {
              if (!window.confirm(`زیردسته «${row.name}» حذف شود؟`)) return;
              deleteSub.mutate(row.id);
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
          <h1 className="text-lg font-black text-slate-900">دسته‌بندی‌ها</h1>
          <p className="mt-1 text-xs text-slate-500">مدیریت دسته‌ها و زیردسته‌های خدمات</p>
        </div>
        <Button onClick={openCreate}>افزودن دسته</Button>
      </div>

      <DataTable
        columns={columns}
        rows={filtered}
        rowKey={(row) => row.id}
        loading={isLoading}
        error={error ? errorMessage(error) : null}
        empty="دسته‌ای پیدا نشد."
        minWidthClassName="min-w-[820px]"
        toolbar={
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="جستجوی دسته…"
            aria-label="جستجوی دسته"
          />
        }
      />

      {formMode && (
        <AdminModal
          title={formMode === "create" ? "افزودن دسته" : "ویرایش دسته"}
          onClose={() => setFormMode(null)}
        >
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-xs text-slate-500">
              نام
              <Input
                required
                value={form.name}
                onChange={(event) => setForm({ ...form, name: event.target.value })}
              />
            </label>
            <label className="space-y-1 text-xs text-slate-500">
              شناسه (slug)
              <Input
                required
                dir="ltr"
                className="text-left"
                pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
                title="فقط حروف انگلیسی کوچک، عدد و خط تیره"
                placeholder="restaurant"
                value={form.slug}
                onChange={(event) => setForm({ ...form, slug: event.target.value.toLowerCase() })}
              />
            </label>
            <label className="space-y-1 text-xs text-slate-500">
              آیکن
              <Input
                value={form.icon}
                onChange={(event) => setForm({ ...form, icon: event.target.value })}
              />
            </label>
            <label className="space-y-1 text-xs text-slate-500">
              ترتیب
              <Input
                type="number"
                value={form.sort_order}
                onChange={(event) =>
                  setForm({ ...form, sort_order: Number(event.target.value) })
                }
              />
            </label>
            <label className="flex items-center gap-2 self-end text-sm text-slate-700">
              <input
                type="checkbox"
                checked={form.is_active}
                onChange={(event) => setForm({ ...form, is_active: event.target.checked })}
              />
              فعال
            </label>
            <div className="flex gap-2 sm:col-span-2">
              <Button type="submit" loading={saveCategory.isPending}>
                ذخیره
              </Button>
              <Button type="button" variant="ghost" onClick={() => setFormMode(null)}>
                انصراف
              </Button>
            </div>
          </form>
        </AdminModal>
      )}

      {subCategory && (
        <AdminModal
          title={`زیردسته‌های ${subCategory.name}`}
          onClose={() => setSubCategory(null)}
          className="max-w-4xl"
        >
          <form
            className="mb-4 grid gap-2 sm:grid-cols-[1fr_1fr_6rem_6rem_auto]"
            onSubmit={(event) => {
              event.preventDefault();
              saveSub.mutate();
            }}
          >
            <Input
              required
              placeholder="نام زیردسته"
              value={subForm.name}
              onChange={(event) => setSubForm({ ...subForm, name: event.target.value })}
            />
            <Input
              required
              dir="ltr"
              className="text-left"
              placeholder="slug"
              pattern="[a-z0-9]+(?:-[a-z0-9]+)*"
              title="فقط حروف انگلیسی کوچک، عدد و خط تیره"
              value={subForm.slug}
              onChange={(event) => setSubForm({ ...subForm, slug: event.target.value.toLowerCase() })}
            />
            <Input
              placeholder="آیکن"
              value={subForm.icon}
              onChange={(event) => setSubForm({ ...subForm, icon: event.target.value })}
            />
            <Input
              type="number"
              placeholder="ترتیب"
              value={subForm.sort_order}
              onChange={(event) =>
                setSubForm({ ...subForm, sort_order: Number(event.target.value) })
              }
            />
            <Button type="submit" loading={saveSub.isPending}>
              {subEditingId ? "ذخیره" : "افزودن"}
            </Button>
          </form>
          <DataTable
            columns={subColumns}
            rows={subCategory.subcategories}
            rowKey={(row) => row.id}
            empty="زیردسته‌ای ثبت نشده است."
            minWidthClassName="min-w-[500px]"
          />
        </AdminModal>
      )}
    </div>
  );
}
