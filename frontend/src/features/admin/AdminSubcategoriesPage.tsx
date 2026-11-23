import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button, Spinner } from "@/components/ui/button";
import { ConfirmSheet } from "@/components/ui/confirm-sheet";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useApi } from "@/lib/query";
import { MAX_VISIBLE_TAGS } from "@/features/business/create/types";
import { AdminModal } from "@/features/admin/AdminModal";
import { DataTable, type DataColumn } from "@/features/admin/data-table";

interface SubcategoryRow {
  id: number;
  category_id: number;
  name: string;
  slug: string;
  icon: string;
  sort_order: number;
  standard_tags: string[];
  visible_tags: string[] | null;
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

const EMPTY_SUB = { name: "", slug: "", icon: "❓", sort_order: 0 };

type ConfirmAction =
  | { kind: "delete"; subcategory: SubcategoryRow }
  | { kind: "remove-tag"; subcategory: SubcategoryRow; tag: string }
  | { kind: "sync"; subcategory: SubcategoryRow };

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

export default function AdminSubcategoriesPage() {
  const { categoryId } = useParams();
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useApi<{ items: CategoryRow[] }>(
    ["admin", "categories"],
    "/admin/categories",
  );

  const category = data?.items.find((item) => item.id === Number(categoryId)) ?? null;
  const [formMode, setFormMode] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<SubcategoryRow | null>(null);
  const [form, setForm] = useState(EMPTY_SUB);
  const [tagTargetId, setTagTargetId] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const [confirmAction, setConfirmAction] = useState<ConfirmAction | null>(null);

  const tagTarget =
    category?.subcategories.find((item) => item.id === tagTargetId) ?? null;

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "categories"] });
    void queryClient.invalidateQueries({ queryKey: ["categories"] });
  }

  const saveSub = useMutation({
    mutationFn: () =>
      editing
        ? api(`/admin/subcategories/${editing.id}`, {
            method: "PATCH",
            body: JSON.stringify(form),
          })
        : api("/admin/subcategories", {
            method: "POST",
            body: JSON.stringify({ ...form, category_id: category?.id }),
          }),
    onSuccess: () => {
      toast(editing ? "زیردسته ذخیره شد." : "زیردسته ساخته شد.");
      setFormMode(null);
      setEditing(null);
      setForm(EMPTY_SUB);
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const deleteSub = useMutation({
    mutationFn: (id: number) => api(`/admin/subcategories/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast("زیردسته حذف شد.");
      setConfirmAction(null);
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const updateTags = useMutation({
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
      setConfirmAction(null);
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const syncTags = useMutation({
    mutationFn: (id: number) =>
      api<{
        businesses: number;
        changed: number;
        tags_added: number;
        tags_removed: number;
      }>(`/admin/subcategories/${id}/sync-tags`, { method: "POST" }),
    onSuccess: (result) => {
      toast(
        result.businesses === 0
          ? "کسب‌وکاری به این زیردسته وصل نیست."
          : result.changed === 0
            ? `${result.businesses} کسب‌وکار بررسی شد؛ همه از قبل همگام بودند.`
            : `${result.changed} از ${result.businesses} کسب‌وکار همگام شد؛ ${result.tags_added} برچسب اضافه و ${result.tags_removed} برچسب حذف شد.`,
      );
      setConfirmAction(null);
      invalidate();
      void queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  function openCreate() {
    setForm(EMPTY_SUB);
    setEditing(null);
    setFormMode("create");
  }

  function openEdit(row: SubcategoryRow) {
    setForm({
      name: row.name,
      slug: row.slug,
      icon: row.icon,
      sort_order: row.sort_order,
    });
    setEditing(row);
    setFormMode("edit");
  }

  function submit(event: FormEvent) {
    event.preventDefault();
    saveSub.mutate();
  }

  function addTags(event: FormEvent) {
    event.preventDefault();
    if (!tagTarget) return;
    const names = parseTags(draft);
    if (names.length === 0) {
      toast("برچسبی برای افزودن وارد نشده است.");
      return;
    }
    const fresh = names.filter((name) => !tagTarget.standard_tags.includes(name));
    if (fresh.length === 0) {
      toast("این برچسب‌ها از قبل برای زیردسته ثبت شده‌اند.");
      setDraft("");
      return;
    }
    updateTags.mutate({
      id: tagTarget.id,
      body: {
        standard_tags: Array.from(new Set([...tagTarget.standard_tags, ...fresh])),
      },
      message: `${fresh.length} برچسب اضافه شد.`,
    });
    setDraft("");
  }

  function toggleVisible(tag: string) {
    if (!tagTarget) return;
    const current = visibleTagsOf(tagTarget);
    const next = current.includes(tag)
      ? current.filter((item) => item !== tag)
      : [...current, tag];
    if (next.length > MAX_VISIBLE_TAGS) {
      toast(`حداکثر ${MAX_VISIBLE_TAGS} برچسب می‌تواند به کاربر نمایش داده شود.`);
      return;
    }
    updateTags.mutate({
      id: tagTarget.id,
      body: { visible_tags: next },
      message: "تنظیم نمایش برچسب ذخیره شد.",
    });
  }

  function askRemoveTag(tag: string) {
    if (!tagTarget) return;
    setConfirmAction({ kind: "remove-tag", subcategory: tagTarget, tag });
  }

  function askSync() {
    if (!tagTarget) return;
    setConfirmAction({ kind: "sync", subcategory: tagTarget });
  }

  function runConfirm() {
    const action = confirmAction;
    if (!action) return;
    if (action.kind === "delete") {
      deleteSub.mutate(action.subcategory.id);
    } else if (action.kind === "remove-tag") {
      updateTags.mutate({
        id: action.subcategory.id,
        body: {
          standard_tags: action.subcategory.standard_tags.filter(
            (item) => item !== action.tag,
          ),
        },
        message: "برچسب حذف شد.",
      });
    } else {
      syncTags.mutate(action.subcategory.id);
    }
  }

  const columns: DataColumn<SubcategoryRow>[] = [
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
      key: "tags",
      header: "برچسب‌ها",
      cell: (row) => (
        <span className="text-xs text-slate-600">
          {row.standard_tags.length} برچسب
          <span className="mx-1 text-slate-300">·</span>
          {visibleTagsOf(row).length} نمایش
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
              setDraft("");
              setTagTargetId(row.id);
            }}
          >
            برچسب‌ها
          </Button>
          <Button size="sm" onClick={() => openEdit(row)}>
            ویرایش
          </Button>
          <Button
            size="sm"
            variant="danger"
            disabled={deleteSub.isPending}
            onClick={() => setConfirmAction({ kind: "delete", subcategory: row })}
          >
            حذف
          </Button>
        </div>
      ),
    },
  ];

  if (isLoading) {
    return (
      <div className="flex justify-center py-12 text-brand-600">
        <Spinner />
      </div>
    );
  }

  if (error) {
    return (
      <div className="rounded-2xl border border-rose-200 bg-white p-6 text-center text-sm text-rose-600">
        {errorMessage(error)}
      </div>
    );
  }

  if (!category) {
    return (
      <div className="rounded-2xl border border-slate-200 bg-white p-6 text-center text-sm text-slate-600">
        دسته انتخاب‌شده پیدا نشد.{" "}
        <Link to="/admin/categories" className="font-medium text-brand-700 hover:underline">
          بازگشت به دسته‌بندی‌ها
        </Link>
      </div>
    );
  }

  const visibleTags = tagTarget ? visibleTagsOf(tagTarget) : [];
  const confirmLoading =
    deleteSub.isPending || updateTags.isPending || syncTags.isPending;
  const confirmTitle =
    confirmAction?.kind === "delete"
      ? "حذف زیردسته"
      : confirmAction?.kind === "remove-tag"
        ? "حذف برچسب"
        : "همگام‌سازی برچسب‌ها";
  const confirmDescription =
    confirmAction?.kind === "delete"
      ? `آیا زیردسته «${confirmAction.subcategory.name}» حذف شود؟`
      : confirmAction?.kind === "remove-tag"
        ? `برچسب «${confirmAction.tag}» از این زیردسته حذف شود؟`
        : confirmAction?.kind === "sync"
          ? `برچسب‌های «${confirmAction.subcategory.name}» روی کسب‌وکارهای این زیردسته همگام شوند؟ برچسب‌های حذف‌شده از کسب‌وکارها برداشته می‌شوند.`
          : "";

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <Link
            to="/admin/categories"
            className="text-xs font-medium text-brand-700 hover:underline"
          >
            ← بازگشت به دسته‌بندی‌ها
          </Link>
          <h1 className="mt-1 text-lg font-black text-slate-900">
            {category.icon} زیردسته‌های {category.name}
          </h1>
          <p className="mt-1 text-xs text-slate-500">
            مدیریت زیردسته‌ها و برچسب‌های هر زیردسته
          </p>
        </div>
        <Button onClick={openCreate}>افزودن زیردسته</Button>
      </div>

      <DataTable
        columns={columns}
        rows={category.subcategories}
        rowKey={(row) => row.id}
        empty="زیردسته‌ای ثبت نشده است."
        minWidthClassName="min-w-[700px]"
      />

      {formMode && (
        <AdminModal
          title={formMode === "create" ? "افزودن زیردسته" : "ویرایش زیردسته"}
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
                placeholder="plumber"
                value={form.slug}
                onChange={(event) =>
                  setForm({ ...form, slug: event.target.value.toLowerCase() })
                }
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
            <div className="flex gap-2 sm:col-span-2">
              <Button type="submit" loading={saveSub.isPending}>
                ذخیره
              </Button>
              <Button type="button" variant="ghost" onClick={() => setFormMode(null)}>
                انصراف
              </Button>
            </div>
          </form>
        </AdminModal>
      )}

      <BottomSheet
        open={tagTarget !== null}
        title={tagTarget ? `برچسب‌های ${tagTarget.icon} ${tagTarget.name}` : ""}
        onClose={() => setTagTargetId(null)}
        footer={
          tagTarget ? (
            <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
              <p className="text-[11px] leading-5 text-slate-500">
                همگام‌سازی، برچسب‌های فعلی زیردسته را روی کسب‌وکارهای آن اعمال می‌کند.
              </p>
              <Button
                variant="outline"
                loading={syncTags.isPending}
                disabled={updateTags.isPending}
                onClick={askSync}
                className="shrink-0"
              >
                همگام‌سازی با کسب‌وکارها
              </Button>
            </div>
          ) : undefined
        }
      >
        {tagTarget && (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2 text-[11px]">
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                {tagTarget.standard_tags.length} برچسب
              </span>
              <span className="rounded-full bg-emerald-50 px-2.5 py-1 text-emerald-700">
                {visibleTags.length} از {MAX_VISIBLE_TAGS} نمایش
              </span>
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-slate-600">
                {Math.max(0, tagTarget.standard_tags.length - visibleTags.length)} فقط جستجو
              </span>
            </div>

            <form onSubmit={addTags} className="flex flex-col gap-2 sm:flex-row">
              <Input
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                placeholder="برچسب جدید؛ چند مورد را با کاما جدا کنید"
                aria-label="افزودن برچسب"
              />
              <Button
                type="submit"
                loading={updateTags.isPending}
                className="shrink-0"
              >
                افزودن
              </Button>
            </form>

            {tagTarget.standard_tags.length === 0 ? (
              <p className="rounded-2xl border border-dashed border-slate-200 p-6 text-center text-sm text-slate-500">
                برای این زیردسته برچسبی ثبت نشده است.
              </p>
            ) : (
              <div className="flex flex-wrap gap-2">
                {tagTarget.standard_tags.map((tag) => {
                  const isVisible = visibleTags.includes(tag);
                  return (
                    <div
                      key={tag}
                      className={cn(
                        "inline-flex items-center gap-1 rounded-full border py-1 pe-1 ps-2.5 text-xs",
                        isVisible
                          ? "border-emerald-200 bg-emerald-50 text-emerald-800"
                          : "border-dashed border-slate-300 bg-slate-50 text-slate-600",
                      )}
                    >
                      <button
                        type="button"
                        onClick={() => toggleVisible(tag)}
                        disabled={updateTags.isPending}
                        aria-pressed={isVisible}
                        aria-label={
                          isVisible
                            ? `پنهان کردن ${tag} از فرم`
                            : `نمایش ${tag} در فرم`
                        }
                        title={isVisible ? "نمایش در فرم" : "فقط جستجو"}
                        className="rounded-full px-0.5 leading-none transition-opacity hover:opacity-70 disabled:opacity-50"
                      >
                        {isVisible ? "👁" : "⌕"}
                      </button>
                      <span className="font-medium">{tag}</span>
                      <button
                        type="button"
                        onClick={() => askRemoveTag(tag)}
                        disabled={updateTags.isPending}
                        aria-label={`حذف ${tag}`}
                        title={`حذف ${tag}`}
                        className="flex h-5 w-5 items-center justify-center rounded-full text-slate-400 transition-colors hover:bg-rose-50 hover:text-rose-600 disabled:opacity-50"
                      >
                        ×
                      </button>
                    </div>
                  );
                })}
              </div>
            )}

            <p className="text-[11px] leading-5 text-slate-500">
              👁 برچسب‌هایی که در فرم افزودن کسب‌وکار دیده می‌شوند؛ ⌕ برچسب‌هایی که
              فقط برای جستجو به کسب‌وکار وصل می‌شوند. حداکثر {MAX_VISIBLE_TAGS} برچسب
              را می‌توانید نمایش دهید.
            </p>
          </div>
        )}
      </BottomSheet>

      <ConfirmSheet
        open={confirmAction !== null}
        title={confirmTitle}
        description={confirmDescription}
        confirmLabel={confirmAction?.kind === "sync" ? "همگام‌سازی" : "حذف"}
        tone={confirmAction?.kind === "delete" ? "rose" : "brand"}
        loading={confirmLoading}
        onClose={() => setConfirmAction(null)}
        onConfirm={runConfirm}
      />
    </div>
  );
}
