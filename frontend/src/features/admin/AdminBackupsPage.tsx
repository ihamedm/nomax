import { useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { fa } from "@/lib/format";
import { formatJalaliDateTime, formatRelative } from "@/lib/jalali";
import { useApi } from "@/lib/query";
import { tokens } from "@/lib/tokens";
import { AdminModal } from "@/features/admin/AdminModal";

interface BackupUpload {
  status: "uploaded" | "failed" | "not_configured" | "skipped" | "already_uploaded";
  key?: string;
  size?: number;
  error?: string;
}

interface BackupItem {
  filename: string;
  size: number;
  created_at: string;
  kind: "manual" | "auto" | "uploaded" | "pre-restore";
  kind_label: string;
  remote: boolean;
  upload?: BackupUpload;
}

interface S3Info {
  configured: boolean;
  bucket: string;
  prefix: string;
  keep_remote: number;
  daily_enabled: boolean;
  daily_time: string;
  daily_timezone: string;
  error: string | null;
}

interface BackupList {
  items: BackupItem[];
  max_upload_mb: number;
  restart_recommended: boolean;
  s3: S3Info;
}

interface SyncResult {
  configured: boolean;
  uploaded: Array<{ filename: string; key: string; size: number }>;
  failed: Array<{ filename: string; error?: string }>;
  pruned: string[];
}

const KIND_TONES: Record<BackupItem["kind"], "brand" | "amber" | "sky" | "slate"> = {
  manual: "brand",
  auto: "sky",
  uploaded: "slate",
  "pre-restore": "amber",
};

const API_BASE = `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/v1`;

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${fa(bytes)} بایت`;
  if (bytes < 1024 * 1024) return `${fa((bytes / 1024).toFixed(1)).replace(".", "٫")} کیلوبایت`;
  return `${fa((bytes / (1024 * 1024)).toFixed(1)).replace(".", "٫")} مگابایت`;
}

function CloudIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-4 w-4"
      aria-hidden
    >
      <path d="M7 18h10a4 4 0 0 0 .8-7.9A6 6 0 0 0 6.3 8.7 4.5 4.5 0 0 0 7 18Z" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      <path d="M12 3 2.5 20h19L12 3Z" />
      <path d="M12 9v5M12 17.5h.01" />
    </svg>
  );
}

export default function AdminBackupsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [restoreTarget, setRestoreTarget] = useState<BackupItem | null>(null);
  const [restoreConfirm, setRestoreConfirm] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadConfirm, setUploadConfirm] = useState("");
  const [downloading, setDownloading] = useState<string | null>(null);

  const backups = useApi<BackupList>(["admin", "backups"], "/admin/backups");
  const items = backups.data?.items ?? [];

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "backups"] });
  }

  const createBackup = useMutation({
    mutationFn: () => api<BackupItem>("/admin/backups", { method: "POST" }),
    onSuccess: (backup) => {
      if (backup.upload?.status === "uploaded") {
        toast(
          `نسخه پشتیبان ساخته و فشرده شد (${formatBytes(backup.size)} → ${formatBytes(
            backup.upload.size ?? 0,
          )}) و در S3 آروان ذخیره شد.`,
        );
      } else if (backup.upload?.status === "failed") {
        toast("نسخه محلی ساخته شد، اما ارسال فشرده به S3 آروان انجام نشد.");
      } else if (backup.upload?.status === "not_configured") {
        toast("نسخه پشتیبان محلی ساخته شد؛ S3 آروان تنظیم نشده است.");
      } else {
        toast(`نسخه پشتیبان ساخته شد (${formatBytes(backup.size)}).`);
      }
      invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  const syncS3 = useMutation({
    mutationFn: () => api<SyncResult>("/admin/backups/sync-s3", { method: "POST" }),
    onSuccess: (result) => {
      if (result.failed.length > 0) {
        toast(
          `${fa(result.uploaded.length)} نسخه ارسال شد؛ ${fa(result.failed.length)} نسخه ناموفق بود.`,
        );
      } else if (result.uploaded.length > 0) {
        toast(`${fa(result.uploaded.length)} نسخه فشرده در S3 آروان ذخیره شد.`);
      } else {
        toast("همه نسخه‌های دستی و خودکار در S3 آروان موجودند.");
      }
      invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  const deleteBackup = useMutation({
    mutationFn: (filename: string) =>
      api(`/admin/backups/${encodeURIComponent(filename)}`, { method: "DELETE" }),
    onSuccess: () => {
      toast("نسخه پشتیبان حذف شد.");
      invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  const restoreSaved = useMutation({
    mutationFn: (backup: BackupItem) => {
      const form = new FormData();
      form.append("confirm", restoreConfirm);
      return api<{ restored: string; safety_backup: string; restart_recommended: boolean }>(
        `/admin/backups/${encodeURIComponent(backup.filename)}/restore`,
        { method: "POST", body: form },
      );
    },
    onSuccess: (result) => {
      toast(
        `بازیابی انجام شد. نسخه ایمنی: ${result.safety_backup}. در صورت مشاهده خطا، سرویس API را یک‌بار ری‌استارت کنید.`,
      );
      setRestoreTarget(null);
      setRestoreConfirm("");
      invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  const restoreUpload = useMutation({
    mutationFn: () => {
      if (!uploadFile) throw new Error("backup file required");
      const form = new FormData();
      form.append("confirm", uploadConfirm);
      form.append("file", uploadFile);
      return api<{ restored: string; safety_backup: string; restart_recommended: boolean }>(
        "/admin/backups/restore-upload",
        { method: "POST", body: form },
      );
    },
    onSuccess: (result) => {
      toast(
        `فایل با موفقیت بازیابی شد. نسخه ایمنی: ${result.safety_backup}. در صورت مشاهده خطا، سرویس API را یک‌بار ری‌استارت کنید.`,
      );
      setUploadFile(null);
      setUploadConfirm("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      invalidate();
    },
    onError: (error: ApiError) => toast(errorMessage(error)),
  });

  async function downloadBackup(backup: BackupItem) {
    setDownloading(backup.filename);
    try {
      const response = await fetch(
        `${API_BASE}/admin/backups/${encodeURIComponent(backup.filename)}/download`,
        {
          headers: tokens.access ? { Authorization: `Bearer ${tokens.access}` } : {},
        },
      );
      if (!response.ok) throw new Error("download failed");
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const anchor = document.createElement("a");
      anchor.href = url;
      anchor.download = backup.filename;
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 1000);
    } catch {
      toast("دانلود نسخه پشتیبان انجام نشد.");
    } finally {
      setDownloading(null);
    }
  }

  function remove(backup: BackupItem) {
    if (!window.confirm(`نسخه پشتیبان «${backup.filename}» حذف شود؟`)) return;
    deleteBackup.mutate(backup.filename);
  }

  const uploadReady = Boolean(uploadFile) && uploadConfirm.trim() === "RESTORE";
  const savedReady = restoreConfirm.trim() === "RESTORE";

  return (
    <div className="space-y-4">
      <header className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">پشتیبان‌گیری پایگاه داده</h1>
          <p className="mt-1 text-xs leading-6 text-slate-500">
            ساخت، دانلود و بازیابی نسخه کامل PostgreSQL. این بخش فقط برای مدیر کل است.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={() => void backups.refetch()}>
            به‌روزرسانی
          </Button>
          <Button
            size="sm"
            variant="outline"
            loading={syncS3.isPending}
            disabled={!backups.data?.s3.configured}
            onClick={() => syncS3.mutate()}
          >
            آرشیو در S3
          </Button>
          <Button
            size="sm"
            loading={createBackup.isPending}
            onClick={() => createBackup.mutate()}
          >
            ایجاد نسخه پشتیبان
          </Button>
        </div>
      </header>

      {backups.data?.s3 && !backups.data.s3.configured && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-3 py-2 text-[10px] leading-5 text-amber-800">
          آرشیو ابری غیرفعال است. پس از تنظیم کلیدهای S3، نسخه‌های دستی و خودکار
          به‌صورت فشرده در باکت خصوصی آروان ذخیره می‌شوند.
        </div>
      )}
      {backups.data?.s3?.error && (
        <div className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-[10px] leading-5 text-rose-700">
          فهرست آرشیو S3 در این لحظه خوانده نشد؛ وضعیت نسخه‌های محلی معتبر است.
        </div>
      )}

      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.55fr)_minmax(320px,0.9fr)]">
        <section className="overflow-hidden rounded-2xl border border-slate-200 bg-white">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-4 py-3">
            <div>
              <h2 className="text-sm font-black text-slate-900">نسخه‌های ذخیره‌شده</h2>
              <p className="mt-0.5 text-[10px] leading-5 text-slate-400">
                نسخه‌های دستی و خودکار، فشرده‌شده در S3 خصوصی آروان هم نگهداری می‌شوند.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-1.5">
              {backups.data?.s3.daily_enabled && (
                <span className="rounded-full bg-brand-50 px-2.5 py-1 text-[10px] font-bold text-brand-700">
                  خودکار روزانه {fa(backups.data.s3.daily_time)}
                </span>
              )}
              <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] font-bold text-slate-600">
                {fa(items.length)} نسخه
              </span>
            </div>
          </div>

          {backups.isLoading && (
            <div className="flex justify-center py-16 text-brand-600">
              <Spinner />
            </div>
          )}

          {backups.error && (
            <p className="m-4 rounded-xl bg-rose-50 px-3 py-2 text-xs text-rose-700">
              {errorMessage(backups.error)}
            </p>
          )}

          {!backups.isLoading && !backups.error && items.length === 0 && (
            <div className="px-4 py-12 text-center">
              <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
                <WarningIcon />
              </span>
              <p className="mt-3 text-sm font-bold text-slate-800">هنوز نسخه‌ای ساخته نشده</p>
              <p className="mt-1 text-[11px] leading-6 text-slate-400">
                اولین نسخه پشتیبان را با دکمه بالا بسازید.
              </p>
            </div>
          )}

          <div className="divide-y divide-slate-100">
            {items.map((backup) => (
              <article key={backup.filename} className="flex flex-wrap items-center gap-3 px-4 py-3">
                <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-slate-500">
                  <svg
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.8"
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    className="h-5 w-5"
                    aria-hidden
                  >
                    <path d="M4 7h16v13H4zM7 7V4h10v3M8 11h8M8 15h5" />
                  </svg>
                </span>
                <div className="min-w-0 flex-1">
                  <div className="flex flex-wrap items-center gap-1.5">
                    <p className="text-[11px] font-bold text-slate-800" dir="ltr">
                      {backup.filename}
                    </p>
                    <Badge tone={KIND_TONES[backup.kind]}>{backup.kind_label}</Badge>
                    {backup.remote && (
                      <span className="inline-flex items-center gap-1 rounded-full bg-emerald-50 px-2 py-1 text-[10px] font-bold text-emerald-700">
                        <CloudIcon /> S3
                      </span>
                    )}
                  </div>
                  <p className="mt-1 text-[10px] text-slate-400">
                    {formatJalaliDateTime(backup.created_at)} · {formatBytes(backup.size)} ·{" "}
                    {formatRelative(backup.created_at)}
                  </p>
                </div>
                <div className="flex w-full shrink-0 flex-wrap items-center gap-1.5 sm:w-auto">
                  <Button
                    size="sm"
                    variant="outline"
                    loading={downloading === backup.filename}
                    onClick={() => void downloadBackup(backup)}
                  >
                    دانلود
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    className="border-rose-200 text-rose-600 hover:bg-rose-50"
                    onClick={() => {
                      setRestoreConfirm("");
                      setRestoreTarget(backup);
                    }}
                  >
                    بازیابی
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    className="text-slate-400 hover:text-rose-600"
                    disabled={deleteBackup.isPending}
                    onClick={() => remove(backup)}
                  >
                    حذف
                  </Button>
                </div>
              </article>
            ))}
          </div>
        </section>

        <aside className="space-y-4">
          <section className="rounded-2xl border border-rose-200 bg-white p-4">
            <div className="flex items-start gap-2.5">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-rose-50 text-rose-500">
                <WarningIcon />
              </span>
              <div>
                <h2 className="text-sm font-black text-slate-900">بازیابی از فایل</h2>
                <p className="mt-1 text-[10px] leading-5 text-slate-500">
                  فقط فایل SQL ساخته‌شده با <span dir="ltr">pg_dump</span> پذیرفته می‌شود.
                </p>
              </div>
            </div>

            <label className="mt-4 flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-slate-300 bg-slate-50/70 px-3 py-4 text-center transition hover:border-brand-300 hover:bg-brand-50/30">
              <span className="text-xs font-bold text-slate-700">
                {uploadFile ? "فایل انتخاب شد" : "انتخاب فایل پشتیبان"}
              </span>
              <span className="mt-1 text-[10px] text-slate-400">
                {uploadFile
                  ? `${uploadFile.name} · ${formatBytes(uploadFile.size)}`
                  : `حداکثر ${fa(backups.data?.max_upload_mb ?? 512)} مگابایت`}
              </span>
              <input
                ref={fileInputRef}
                type="file"
                accept=".sql,text/plain,application/sql"
                className="sr-only"
                onChange={(event) => {
                  setUploadFile(event.target.files?.[0] ?? null);
                  setUploadConfirm("");
                }}
              />
            </label>

            <label className="mt-3 block">
              <span className="text-[10px] font-bold text-slate-500">
                برای تأیید، عبارت <span dir="ltr">RESTORE</span> را وارد کنید
              </span>
              <Input
                value={uploadConfirm}
                onChange={(event) => setUploadConfirm(event.target.value)}
                placeholder="RESTORE"
                dir="ltr"
                className="mt-1"
                autoComplete="off"
              />
            </label>

            <Button
              variant="danger"
              className="mt-3 w-full"
              disabled={!uploadReady}
              loading={restoreUpload.isPending}
              onClick={() => restoreUpload.mutate()}
            >
              بازیابی پایگاه داده
            </Button>
            <p className="mt-2 text-[9px] leading-5 text-slate-400">
              قبل از بازیابی یک نسخه ایمنی خودکار ساخته می‌شود. بازیابی در یک تراکنش انجام
              می‌شود و در صورت خطا، داده‌ها دست‌نخورده می‌مانند.
            </p>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-4 text-[10px] leading-6 text-slate-500">
            <p className="text-xs font-black text-slate-800">پیش از بازیابی</p>
            <ul className="mt-2 list-disc space-y-1 pr-4">
              <li>در ساعات کم‌ترافیک انجام دهید و صفحه‌های دیگر را ببندید.</li>
              <li>این عملیات اتصال‌های فعلی پایگاه داده را مختل می‌کند.</li>
              <li>پس از بازیابی، در صورت مشاهده خطا سرویس API و worker را ری‌استارت کنید.</li>
              <li>
                نسخه‌های دستی و خودکار روزانه در S3 خصوصی آروان فشرده می‌شوند و{" "}
                {fa(backups.data?.s3.keep_remote ?? 30)} نسخه آخر نگهداری می‌شود.
              </li>
            </ul>
          </section>
        </aside>
      </div>

      {restoreTarget && (
        <AdminModal
          title="بازیابی پایگاه داده"
          className="max-w-lg"
          onClose={() => {
            if (restoreSaved.isPending) return;
            setRestoreTarget(null);
            setRestoreConfirm("");
          }}
        >
          <div className="rounded-xl border border-rose-200 bg-rose-50 p-3 text-[11px] leading-6 text-rose-800">
            تمام داده‌های فعلی با محتوای این نسخه جایگزین می‌شوند. یک نسخه ایمنی خودکار قبل از
            بازیابی ساخته می‌شود.
          </div>
          <p className="mt-3 rounded-xl bg-slate-50 px-3 py-2 text-[10px] text-slate-500">
            فایل: <span dir="ltr">{restoreTarget.filename}</span>
            <br />
            {formatJalaliDateTime(restoreTarget.created_at)} · {formatBytes(restoreTarget.size)}
          </p>
          <label className="mt-4 block">
            <span className="text-[10px] font-bold text-slate-500">
              برای تأیید، عبارت <span dir="ltr">RESTORE</span> را وارد کنید
            </span>
            <Input
              value={restoreConfirm}
              onChange={(event) => setRestoreConfirm(event.target.value)}
              placeholder="RESTORE"
              dir="ltr"
              className="mt-1"
              autoComplete="off"
            />
          </label>
          <div className="mt-4 flex gap-2">
            <Button
              variant="danger"
              className="flex-1"
              disabled={!savedReady}
              loading={restoreSaved.isPending}
              onClick={() => restoreSaved.mutate(restoreTarget)}
            >
              تأیید و بازیابی
            </Button>
            <Button
              variant="outline"
              className="flex-1"
              disabled={restoreSaved.isPending}
              onClick={() => {
                setRestoreTarget(null);
                setRestoreConfirm("");
              }}
            >
              انصراف
            </Button>
          </div>
        </AdminModal>
      )}
    </div>
  );
}
