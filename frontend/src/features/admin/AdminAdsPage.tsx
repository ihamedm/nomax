import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { useApi } from "@/lib/query";
import { AdminModal } from "@/features/admin/AdminModal";
import { DataTable, type DataColumn } from "@/features/admin/data-table";

interface AdRow {
  id: string;
  title: string;
  body?: string | null;
  image_url?: string | null;
  target_url?: string | null;
  placement: string;
  is_active: boolean;
}

const EMPTY = {
  title: "",
  body: "",
  image_url: "",
  target_url: "",
  placement: "home_banner",
  is_active: true,
};

export default function AdminAdsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useApi<{ items: AdRow[] }>(["admin", "ads"], "/admin/ads");
  const [mode, setMode] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<AdRow | null>(null);
  const [form, setForm] = useState(EMPTY);

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "ads"] });
    void queryClient.invalidateQueries({ queryKey: ["ads"] });
  }

  const save = useMutation({
    mutationFn: () =>
      mode === "create"
        ? api("/admin/ads", { method: "POST", body: JSON.stringify(form) })
        : api(`/admin/ads/${editing?.id}`, { method: "PATCH", body: JSON.stringify(form) }),
    onSuccess: () => {
      toast(mode === "create" ? "بنر ساخته شد." : "بنر ذخیره شد.");
      setMode(null);
      setEditing(null);
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const remove = useMutation({
    mutationFn: (id: string) => api(`/admin/ads/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast("بنر حذف شد.");
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  const columns: DataColumn<AdRow>[] = [
    {
      key: "title",
      header: "بنر",
      cell: (row) => (
        <div>
          <p className="font-bold text-slate-900">{row.title}</p>
          <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-400">{row.body || "بدون متن"}</p>
        </div>
      ),
    },
    {
      key: "placement",
      header: "محل نمایش",
      cell: (row) => <span className="text-xs text-slate-600">{row.placement}</span>,
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
        <div className="flex justify-end gap-1">
          <Button
            size="sm"
            onClick={() => {
              setEditing(row);
              setForm({
                title: row.title,
                body: row.body ?? "",
                image_url: row.image_url ?? "",
                target_url: row.target_url ?? "",
                placement: row.placement,
                is_active: row.is_active,
              });
              setMode("edit");
            }}
          >
            ویرایش
          </Button>
          <Button
            size="sm"
            variant="danger"
            onClick={() => {
              if (!window.confirm(`بنر «${row.title}» حذف شود؟`)) return;
              remove.mutate(row.id);
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
          <h1 className="text-lg font-black text-slate-900">بنرها و تبلیغات</h1>
          <p className="mt-1 text-xs text-slate-500">بنرهای صفحه اصلی و محل نمایش آن‌ها</p>
        </div>
        <Button
          onClick={() => {
            setForm(EMPTY);
            setEditing(null);
            setMode("create");
          }}
        >
          افزودن بنر
        </Button>
      </div>

      <DataTable
        columns={columns}
        rows={data?.items ?? []}
        rowKey={(row) => row.id}
        loading={isLoading}
        error={error ? errorMessage(error) : null}
        empty="بنری ثبت نشده است."
        minWidthClassName="min-w-[700px]"
      />

      {mode && (
        <AdminModal title={mode === "create" ? "افزودن بنر" : "ویرایش بنر"} onClose={() => setMode(null)}>
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-xs text-slate-500 sm:col-span-2">
              عنوان
              <Input
                required
                value={form.title}
                onChange={(event) => setForm({ ...form, title: event.target.value })}
              />
            </label>
            <label className="space-y-1 text-xs text-slate-500 sm:col-span-2">
              متن
              <Input
                value={form.body}
                onChange={(event) => setForm({ ...form, body: event.target.value })}
              />
            </label>
            <label className="space-y-1 text-xs text-slate-500">
              آدرس تصویر
              <Input
                dir="ltr"
                value={form.image_url}
                onChange={(event) => setForm({ ...form, image_url: event.target.value })}
              />
            </label>
            <label className="space-y-1 text-xs text-slate-500">
              لینک مقصد
              <Input
                dir="ltr"
                value={form.target_url}
                onChange={(event) => setForm({ ...form, target_url: event.target.value })}
              />
            </label>
            <label className="space-y-1 text-xs text-slate-500">
              محل نمایش
              <select
                value={form.placement}
                onChange={(event) => setForm({ ...form, placement: event.target.value })}
                className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"
              >
                <option value="home_banner">بنر صفحه اصلی</option>
                <option value="home_mid">میانه صفحه اصلی</option>
                <option value="search_top">بالای جستجو</option>
              </select>
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
