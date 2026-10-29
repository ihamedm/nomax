import { useEffect, useMemo, useState, type FormEvent } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { formatJalali } from "@/lib/jalali";
import { useApi, useApiWithMeta } from "@/lib/query";
import { AdminModal } from "@/features/admin/AdminModal";
import { DataTable, type DataColumn } from "@/features/admin/data-table";

type ColumnKind = "string" | "number" | "boolean" | "datetime" | "json";

interface ColumnMeta {
  name: string;
  kind: ColumnKind;
  nullable: boolean;
  primary_key: boolean;
}

interface ModelMeta {
  name: string;
  label: string;
  count: number;
  columns: ColumnMeta[];
}

type Row = Record<string, unknown>;

const HIDDEN_TABLE = new Set(["created_at", "updated_at", "deleted_at"]);
const HIDDEN_FORM = new Set(["created_at", "updated_at", "deleted_at"]);

function displayValue(value: unknown, column: ColumnMeta) {
  if (value === null || value === undefined) return "—";
  if (column.kind === "boolean") return value ? "بله" : "خیر";
  if (column.kind === "datetime" && typeof value === "string") return formatJalali(value);
  if (column.kind === "json") return JSON.stringify(value);
  return String(value);
}

export default function AdminDataPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const models = useApi<{ items: ModelMeta[] }>(["admin", "data", "models"], "/admin/data/models");

  const [selected, setSelected] = useState("");
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const [mode, setMode] = useState<"create" | "edit" | null>(null);
  const [editing, setEditing] = useState<Row | null>(null);
  const [form, setForm] = useState<Record<string, string | boolean>>({});

  useEffect(() => {
    if (!selected && models.data?.items.length) setSelected(models.data.items[0].name);
  }, [models.data, selected]);

  const activeModel = models.data?.items.find((item) => item.name === selected);
  const limit = 25;
  const page = Math.floor(offset / limit) + 1;
  const searchParams = new URLSearchParams({ limit: String(limit), offset: String(offset) });
  if (search.trim()) searchParams.set("q", search.trim());

  const rowsQuery = useApiWithMeta<
    { items: Row[]; columns: ColumnMeta[] },
    { total: number; limit: number; offset: number }
  >(
    ["admin", "data", selected, search, offset],
    `/admin/data/${selected}?${searchParams.toString()}`,
    { enabled: Boolean(selected) },
  );

  const rows = rowsQuery.data?.data.items ?? [];
  const meta = rowsQuery.data?.meta;

  const columns = useMemo(() => {
    if (!activeModel) return [];
    const visible = activeModel.columns.filter(
      (column) => column.primary_key || !HIDDEN_TABLE.has(column.name),
    );
    return visible.slice(0, 8);
  }, [activeModel]);

  const editable = useMemo(
    () =>
      (activeModel?.columns ?? []).filter(
        (column) => !column.primary_key && !HIDDEN_FORM.has(column.name),
      ),
    [activeModel],
  );

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "data"] });
  }

  function openCreate() {
    setEditing(null);
    const initial: Record<string, string | boolean> = {};
    for (const column of editable) initial[column.name] = column.kind === "boolean" ? false : "";
    setForm(initial);
    setMode("create");
  }

  function openEdit(row: Row) {
    setEditing(row);
    const initial: Record<string, string | boolean> = {};
    for (const column of editable) {
      const value = row[column.name];
      if (column.kind === "boolean") initial[column.name] = Boolean(value);
      else if (column.kind === "json")
        initial[column.name] = value === null || value === undefined ? "" : JSON.stringify(value);
      else initial[column.name] = value === null || value === undefined ? "" : String(value);
    }
    setForm(initial);
    setMode("edit");
  }

  const save = useMutation({
    mutationFn: () => {
      const payload: Record<string, unknown> = {};
      for (const column of editable) {
        const value = form[column.name];
        if (value === "") {
          if (column.nullable) payload[column.name] = null;
          continue;
        }
        payload[column.name] = value;
      }
      if (mode === "create") {
        return api(`/admin/data/${selected}`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      const pk = activeModel?.columns.find((column) => column.primary_key)?.name;
      return api(`/admin/data/${selected}/${String(editing?.[pk ?? "id"])}`, {
        method: "PATCH",
        body: JSON.stringify(payload),
      });
    },
    onSuccess: () => {
      toast(mode === "create" ? "رکورد ساخته شد." : "رکورد ذخیره شد.");
      setMode(null);
      setEditing(null);
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const remove = useMutation({
    mutationFn: (row: Row) => {
      const pk = activeModel?.columns.find((column) => column.primary_key)?.name;
      return api(`/admin/data/${selected}/${String(row[pk ?? "id"])}`, { method: "DELETE" });
    },
    onSuccess: () => {
      toast("رکورد حذف شد.");
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  function submit(event: FormEvent) {
    event.preventDefault();
    save.mutate();
  }

  const tableColumns: DataColumn<Row>[] = [
    ...columns.map((column) => ({
      key: column.name,
      header: column.name,
      cell: (row: Row) => (
        <span
          className={
            column.primary_key ? "text-[11px] text-slate-400" : "max-w-64 truncate text-xs text-slate-700"
          }
          dir="ltr"
          title={displayValue(row[column.name], column)}
        >
          {displayValue(row[column.name], column)}
        </span>
      ),
    })),
    {
      key: "_actions",
      header: "عملیات",
      className: "text-left",
      cell: (row) => (
        <div className="flex justify-end gap-1">
          <Button size="sm" onClick={() => openEdit(row)}>
            ویرایش
          </Button>
          <Button
            size="sm"
            variant="danger"
            onClick={() => {
              if (!window.confirm("این رکورد حذف شود؟")) return;
              remove.mutate(row);
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
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">مدل‌های داده</h1>
          <p className="mt-1 text-xs text-slate-500">
            دسترسی کامل مدیر کل به جدول‌های باقی‌مانده پایگاه داده
          </p>
        </div>
        <div className="flex items-center gap-2">
          <select
            value={selected}
            onChange={(event) => {
              setSelected(event.target.value);
              setOffset(0);
              setSearch("");
            }}
            className="h-11 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"
          >
            {(models.data?.items ?? []).map((model) => (
              <option key={model.name} value={model.name}>
                {model.label} ({model.count})
              </option>
            ))}
          </select>
          <Button onClick={openCreate} disabled={!activeModel}>
            افزودن رکورد
          </Button>
        </div>
      </div>

      <DataTable
        columns={tableColumns}
        rows={rows}
        rowKey={(row) => String(row[columns.find((column) => column.primary_key)?.name ?? "id"])}
        loading={rowsQuery.isLoading}
        error={rowsQuery.error ? errorMessage(rowsQuery.error) : null}
        empty="رکوردی پیدا نشد."
        meta={
          meta
            ? {
                page,
                pages: Math.max(1, Math.ceil(meta.total / limit)),
                total: meta.total,
              }
            : undefined
        }
        onPageChange={(next) => setOffset((next - 1) * limit)}
        toolbar={
          <Input
            value={search}
            onChange={(event) => {
              setSearch(event.target.value);
              setOffset(0);
            }}
            placeholder="جستجو در رکوردها…"
            aria-label="جستجوی رکورد"
          />
        }
      />

      {mode && activeModel && (
        <AdminModal
          title={`${mode === "create" ? "افزودن" : "ویرایش"} رکورد ${activeModel.label}`}
          onClose={() => setMode(null)}
        >
          <form onSubmit={submit} className="grid gap-3 sm:grid-cols-2">
            {editable.map((column) => (
              <label
                key={column.name}
                className={
                  column.kind === "json"
                    ? "space-y-1 text-xs text-slate-500 sm:col-span-2"
                    : "space-y-1 text-xs text-slate-500"
                }
              >
                <span>
                  {column.name}
                  {column.nullable ? "" : " *"}
                </span>
                {column.kind === "boolean" ? (
                  <span className="flex h-11 items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={Boolean(form[column.name])}
                      onChange={(event) =>
                        setForm({ ...form, [column.name]: event.target.checked })
                      }
                    />
                    فعال
                  </span>
                ) : column.kind === "json" ? (
                  <textarea
                    value={String(form[column.name] ?? "")}
                    onChange={(event) => setForm({ ...form, [column.name]: event.target.value })}
                    rows={3}
                    dir="ltr"
                    className="w-full rounded-xl border border-slate-200 bg-white px-3 py-2 font-mono text-xs text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                    placeholder='{"key": "value"}'
                  />
                ) : (
                  <Input
                    type={column.kind === "number" ? "number" : "text"}
                    dir={column.kind === "datetime" ? "ltr" : undefined}
                    value={String(form[column.name] ?? "")}
                    onChange={(event) => setForm({ ...form, [column.name]: event.target.value })}
                    placeholder={column.kind === "datetime" ? "2026-01-01T00:00:00+00:00" : ""}
                  />
                )}
              </label>
            ))}
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
