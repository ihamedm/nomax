import { useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { useApi } from "@/lib/query";
import { AdminModal } from "@/features/admin/AdminModal";
import { DataTable, type DataColumn } from "@/features/admin/data-table";

interface TagRow {
  id: number;
  name: string;
  status: string;
  is_custom: boolean;
  usage_count: number;
}

const FILTERS = [
  { label: "همه", value: "" },
  { label: "تأییدشده", value: "approved" },
  { label: "در انتظار", value: "pending" },
  { label: "ردشده", value: "rejected" },
];

const EMPTY = { name: "", status: "approved", is_custom: true };

export default function AdminTagsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useApi<{ items: TagRow[] }>(["admin", "tags"], "/admin/tags");
  const [filter, setFilter] = useState("");
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<TagRow | null>(null);
  const [form, setForm] = useState(EMPTY);

  const items = data?.items ?? [];
  const rows = items.filter(
    (item) =>
      (!filter || item.status === filter) &&
      (!search.trim() || item.name.includes(search.trim())),
  );

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "tags"] });
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
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const remove = useMutation({
    mutationFn: (id: number) => api(`/admin/tags/${id}`, { method: "DELETE" }),
    onSuccess: () => {
      toast("برچسب حذف شد.");
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
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

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">برچسب‌ها</h1>
          <p className="mt-1 text-xs text-slate-500">برچسب‌های خدمت و برچسب‌های سفارشی کسب‌وکارها</p>
        </div>
        <Button
          onClick={() => {
            setForm(EMPTY);
            setEditing(null);
            setMode("create");
          }}
        >
          افزودن برچسب
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        {FILTERS.map((item) => (
          <button
            key={item.value || "all"}
            type="button"
            onClick={() => setFilter(item.value)}
            className={
              filter === item.value
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
        rows={rows}
        rowKey={(row) => row.id}
        loading={isLoading}
        error={error ? errorMessage(error) : null}
        empty="برچسبی پیدا نشد."
        minWidthClassName="min-w-[700px]"
        toolbar={
          <Input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="جستجوی برچسب…"
            aria-label="جستجوی برچسب"
          />
        }
      />

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
