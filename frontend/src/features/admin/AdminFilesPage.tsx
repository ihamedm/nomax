import { useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useApi } from "@/lib/query";
import { DataTable, type DataColumn } from "@/features/admin/data-table";

type Bucket = "public" | "private";

interface StorageEntry {
  type: "folder" | "file";
  name: string;
  key: string;
  size: number;
  last_modified?: string | null;
}

function formatBytes(size: number): string {
  if (size < 1024) return `${size} B`;
  if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`;
  return `${(size / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value?: string | null): string {
  if (!value) return "—";
  try {
    return new Intl.DateTimeFormat("fa-IR", {
      dateStyle: "short",
      timeStyle: "short",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export default function AdminFilesPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [bucket, setBucket] = useState<Bucket>("public");
  const [prefix, setPrefix] = useState("");
  const [folderName, setFolderName] = useState("");

  const queryKey = ["admin", "files", bucket, prefix];
  const { data, isLoading, error } = useApi<{ items: StorageEntry[] }>(
    queryKey,
    `/admin/files?bucket=${bucket}&prefix=${encodeURIComponent(prefix)}`,
  );

  const items = data?.items ?? [];
  const crumbs = useMemo(
    () =>
      prefix
        .split("/")
        .filter(Boolean)
        .map((name, index, all) => ({
          name,
          prefix: `${all.slice(0, index + 1).join("/")}/`,
        })),
    [prefix],
  );

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "files"] });
  }

  function switchBucket(next: Bucket) {
    setBucket(next);
    setPrefix("");
    setFolderName("");
  }

  const createFolder = useMutation({
    mutationFn: () =>
      api("/admin/files/folder", {
        method: "POST",
        body: JSON.stringify({ bucket, prefix, name: folderName }),
      }),
    onSuccess: () => {
      toast("پوشه ساخته شد.");
      setFolderName("");
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const upload = useMutation({
    mutationFn: (file: File) => {
      const form = new FormData();
      form.append("bucket", bucket);
      form.append("prefix", prefix);
      form.append("file", file);
      return api("/admin/files/upload", { method: "POST", body: form });
    },
    onSuccess: () => {
      toast("فایل بارگذاری شد.");
      if (fileInputRef.current) fileInputRef.current.value = "";
      invalidate();
    },
    onError: (err: ApiError) => {
      toast(errorMessage(err));
      if (fileInputRef.current) fileInputRef.current.value = "";
    },
  });

  const remove = useMutation({
    mutationFn: (key: string) => {
      const search = new URLSearchParams({ bucket, key });
      return api(`/admin/files?${search.toString()}`, { method: "DELETE" });
    },
    onSuccess: () => {
      toast("حذف شد.");
      invalidate();
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const copyLink = useMutation({
    mutationFn: (row: StorageEntry) => {
      const search = new URLSearchParams({ bucket, key: row.key });
      return api<{ url: string; expires_in: number | null }>(
        `/admin/files/link?${search.toString()}`,
      );
    },
    onSuccess: async (data) => {
      try {
        await navigator.clipboard.writeText(data.url);
        toast(
          data.expires_in
            ? `لینک موقت ${Math.round(data.expires_in / 60)} دقیقه‌ای کپی شد.`
            : "لینک فایل کپی شد.",
        );
      } catch {
        window.prompt("لینک را کپی کنید:", data.url);
      }
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const columns: DataColumn<StorageEntry>[] = [
    {
      key: "name",
      header: "نام",
      cell: (row) =>
        row.type === "folder" ? (
          <button
            type="button"
            onClick={() => setPrefix(row.key)}
            className="inline-flex items-center gap-2 text-sm font-bold text-slate-900 hover:text-brand-600"
          >
            <span aria-hidden>📁</span>
            {row.name}
          </button>
        ) : (
          <span className="inline-flex items-center gap-2 text-sm text-slate-800">
            <span aria-hidden>📄</span>
            {row.name}
          </span>
        ),
    },
    {
      key: "type",
      header: "نوع",
      cell: (row) => (
        <span className="text-xs text-slate-500">{row.type === "folder" ? "پوشه" : "فایل"}</span>
      ),
    },
    {
      key: "size",
      header: "حجم",
      cell: (row) => (
        <span className="text-xs text-slate-500">
          {row.type === "folder" ? "—" : formatBytes(row.size)}
        </span>
      ),
    },
    {
      key: "modified",
      header: "آخرین تغییر",
      cell: (row) => (
        <span className="text-xs text-slate-400">{formatDate(row.last_modified)}</span>
      ),
    },
    {
      key: "actions",
      header: "عملیات",
      className: "text-left",
      cell: (row) => (
        <div className="flex items-center justify-end gap-1">
          {row.type === "file" && (
            <Button
              size="sm"
              variant="outline"
              disabled={copyLink.isPending && copyLink.variables?.key === row.key}
              onClick={() => copyLink.mutate(row)}
            >
              کپی لینک
            </Button>
          )}
          <Button
            size="sm"
            variant="danger"
            disabled={remove.isPending}
            onClick={() => {
              const label = row.type === "folder" ? "پوشه و همه محتویاتش" : "فایل";
              if (!window.confirm(`حذف ${label} «${row.name}»؟`)) return;
              remove.mutate(row.key);
            }}
          >
            حذف
          </Button>
        </div>
      ),
    },
  ];

  return (
    <div className="space-y-4">
      <div>
        <h1 className="text-lg font-black text-slate-900">مدیریت فایل‌ها</h1>
        <p className="mt-1 text-xs text-slate-500">
          مرور، ساخت و حذف فایل‌ها و پوشه‌های فضای ابری آروان (S3).
        </p>
      </div>

      <div className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex rounded-xl bg-slate-100 p-1">
            {(["public", "private"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => switchBucket(value)}
                className={cn(
                  "rounded-lg px-3 py-1.5 text-xs transition-colors",
                  bucket === value
                    ? "bg-white font-bold text-slate-900 shadow-sm"
                    : "text-slate-500",
                )}
              >
                {value === "public" ? "عمومی" : "خصوصی"}
              </button>
            ))}
          </div>

          <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto text-xs text-slate-500">
            <button type="button" onClick={() => setPrefix("")} className="shrink-0 hover:text-brand-600">
              ریشه
            </button>
            {crumbs.map((crumb) => (
              <span key={crumb.prefix} className="flex shrink-0 items-center gap-1">
                <span className="text-slate-300">/</span>
                <button
                  type="button"
                  onClick={() => setPrefix(crumb.prefix)}
                  className="hover:text-brand-600"
                >
                  {crumb.name}
                </button>
              </span>
            ))}
          </div>
        </div>

        <div className="mt-4 flex flex-wrap items-end gap-2">
          <label className="min-w-48 flex-1 space-y-1 text-xs text-slate-500">
            پوشه جدید
            <Input
              value={folderName}
              onChange={(event) => setFolderName(event.target.value)}
              placeholder="نام پوشه"
              className="h-10 text-sm"
            />
          </label>
          <Button
            size="sm"
            variant="outline"
            loading={createFolder.isPending}
            disabled={!folderName.trim()}
            onClick={() => createFolder.mutate()}
          >
            ساخت پوشه
          </Button>

          <input
            ref={fileInputRef}
            type="file"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) upload.mutate(file);
            }}
          />
          <Button
            size="sm"
            loading={upload.isPending}
            onClick={() => fileInputRef.current?.click()}
          >
            بارگذاری فایل
          </Button>
        </div>
      </div>

      <DataTable
        columns={columns}
        rows={items}
        rowKey={(row) => row.key}
        loading={isLoading}
        error={error ? errorMessage(error) : null}
        empty={prefix ? "این پوشه خالی است." : "فایلی در این فضای ذخیره‌سازی نیست."}
        minWidthClassName="min-w-[700px]"
      />
    </div>
  );
}
