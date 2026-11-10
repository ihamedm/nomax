import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { fa, formatPhone } from "@/lib/format";
import { useApi } from "@/lib/query";

interface RateLimitEntry {
  key: string;
  kind: string;
  subject: string;
  count: number;
  ttl_seconds: number | null;
}

interface BlockEntry {
  kind: "phone" | "ip";
  subject: string;
  ttl_seconds: number | null;
}

interface SecurityStatus {
  rate_limits: RateLimitEntry[];
  blocks: BlockEntry[];
}

const KIND_LABELS: Record<string, string> = {
  register_ip: "ثبت‌نام (IP)",
  check_ip: "بررسی شماره (IP)",
  login_ip: "ورود (IP)",
  password_attempts: "تلاش‌های رمز عبور",
  password_block: "قفل رمز عبور",
  otp_phone: "درخواست کد (شماره)",
  otp_ip: "درخواست کد (IP)",
  otp_attempts: "تلاش‌های کد یکبارمصرف",
};

const BLOCK_LABELS = { phone: "شماره موبایل", ip: "آدرس IP" };

function formatTtl(seconds: number | null): string {
  if (seconds === null) return "دائمی";
  if (seconds < 60) return `${fa(seconds)} ثانیه`;
  if (seconds < 3600) return `${fa(Math.ceil(seconds / 60))} دقیقه`;
  return `${fa(Math.ceil(seconds / 3600))} ساعت`;
}

export function AdminSecurityPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const statusQuery = useApi<SecurityStatus>(["admin", "security"], "/admin/security");
  const [blockKind, setBlockKind] = useState<"phone" | "ip">("phone");
  const [blockValue, setBlockValue] = useState("");
  const [logoutPhone, setLogoutPhone] = useState("");

  const status = statusQuery.data;

  function refresh() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "security"] });
  }

  const resetKey = useMutation({
    mutationFn: (key: string) =>
      api("/admin/security/rate-limits/reset", {
        method: "POST",
        body: JSON.stringify({ key }),
      }),
    onSuccess: () => {
      toast("محدودیت پاک شد.");
      refresh();
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const resetAll = useMutation({
    mutationFn: () =>
      api("/admin/security/rate-limits/reset-all", {
        method: "POST",
        body: JSON.stringify({}),
      }),
    onSuccess: () => {
      toast("همه محدودیت‌ها پاک شدند.");
      refresh();
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const block = useMutation({
    mutationFn: () =>
      api("/admin/security/blocks", {
        method: "POST",
        body: JSON.stringify({ kind: blockKind, value: blockValue }),
      }),
    onSuccess: () => {
      toast(blockKind === "phone" ? "شماره مسدود شد." : "آی‌پی مسدود شد.");
      setBlockValue("");
      refresh();
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const unblock = useMutation({
    mutationFn: (entry: BlockEntry) =>
      api(`/admin/security/blocks/${entry.kind}/${encodeURIComponent(entry.subject)}`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      toast("محدودیت برداشته شد.");
      refresh();
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const forceLogout = useMutation({
    mutationFn: () =>
      api("/admin/security/users/logout", {
        method: "POST",
        body: JSON.stringify({ phone: logoutPhone }),
      }),
    onSuccess: () => {
      toast("نشست‌های کاربر باطل شد.");
      setLogoutPhone("");
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const busy = resetKey.isPending || resetAll.isPending || block.isPending || unblock.isPending;
  const loading = statusQuery.isLoading;
  const error = statusQuery.error ? errorMessage(statusQuery.error) : null;

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">امنیت و محدودیت‌ها</h1>
          <p className="mt-1 max-w-2xl text-xs leading-6 text-slate-500">
            محدودیت‌های خودکار ورود، ثبت‌نام و ارسال کد را ببینید و پاک کنید، شماره یا
            آی‌پی را مسدود کنید، یا نشست‌های یک کاربر را باطل کنید.
          </p>
        </div>
        <Button
          size="sm"
          variant="outline"
          disabled={busy || loading}
          onClick={() => void statusQuery.refetch()}
        >
          به‌روزرسانی
        </Button>
      </header>

      {error && <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}

      <article className="rounded-2xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h2 className="text-sm font-bold text-slate-900">محدودیت‌های فعال</h2>
            <p className="mt-1 text-[11px] leading-6 text-slate-500">
              این شمارنده‌ها با هر تلاش افزایش می‌یابند و پس از پایان زمان، خودکار پاک
              می‌شوند.
            </p>
          </div>
          <Button
            size="sm"
            variant="outline"
            disabled={busy || loading || !(status?.rate_limits.length ?? 0)}
            loading={resetAll.isPending}
            onClick={() => resetAll.mutate()}
          >
            پاک کردن همه
          </Button>
        </div>

        <div className="mt-4 space-y-2">
          {loading ? (
            <p className="text-xs text-slate-400">در حال بارگذاری…</p>
          ) : status?.rate_limits.length ? (
            status.rate_limits.map((entry) => (
              <div
                key={entry.key}
                className="flex flex-wrap items-center gap-2 rounded-xl border border-slate-100 bg-slate-50/60 px-3 py-2"
              >
                <Badge tone="slate">{KIND_LABELS[entry.kind] ?? entry.kind}</Badge>
                <span dir="ltr" className="text-xs font-bold text-slate-800">
                  {entry.kind.includes("phone") || entry.kind.includes("attempts") || entry.kind.includes("block")
                    ? formatPhone(entry.subject)
                    : entry.subject}
                </span>
                <span className="text-[11px] text-slate-500">
                  {fa(entry.count)} تلاش · {formatTtl(entry.ttl_seconds)} مانده
                </span>
                <Button
                  size="sm"
                  variant="ghost"
                  className="mr-auto text-rose-600"
                  disabled={busy}
                  loading={resetKey.isPending && resetKey.variables === entry.key}
                  onClick={() => resetKey.mutate(entry.key)}
                >
                  پاک کردن
                </Button>
              </div>
            ))
          ) : (
            <p className="rounded-xl border border-dashed border-slate-200 px-4 py-6 text-center text-xs text-slate-400">
              محدودیت فعالی وجود ندارد.
            </p>
          )}
        </div>
      </article>

      <article className="rounded-2xl border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-bold text-slate-900">مسدودسازی دستی</h2>
        <p className="mt-1 text-[11px] leading-6 text-slate-500">
          شماره یا آی‌پی مسدودشده نمی‌تواند وارد شود، ثبت‌نام کند یا کد دریافت کند.
        </p>

        <form
          className="mt-3 flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (blockValue.trim()) block.mutate();
          }}
        >
          <select
            value={blockKind}
            onChange={(event) => setBlockKind(event.target.value as "phone" | "ip")}
            className="h-12 rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"
          >
            <option value="phone">{BLOCK_LABELS.phone}</option>
            <option value="ip">{BLOCK_LABELS.ip}</option>
          </select>
          <Input
            value={blockValue}
            onChange={(event) => setBlockValue(event.target.value)}
            placeholder={blockKind === "phone" ? "۰۹۱۲…" : "1.2.3.4"}
            dir="ltr"
            className="h-12 w-full flex-1 text-left sm:w-auto"
          />
          <Button type="submit" size="sm" disabled={busy} loading={block.isPending}>
            مسدود کن
          </Button>
        </form>

        <div className="mt-4 space-y-2">
          {status?.blocks.length ? (
            status.blocks.map((entry) => (
              <div
                key={`${entry.kind}:${entry.subject}`}
                className="flex flex-wrap items-center gap-2 rounded-xl border border-rose-100 bg-rose-50/60 px-3 py-2"
              >
                <Badge tone="rose">{BLOCK_LABELS[entry.kind]}</Badge>
                <span dir="ltr" className="text-xs font-bold text-slate-800">
                  {entry.kind === "phone" ? formatPhone(entry.subject) : entry.subject}
                </span>
                <span className="text-[11px] text-slate-500">{formatTtl(entry.ttl_seconds)}</span>
                <Button
                  size="sm"
                  variant="ghost"
                  className="mr-auto text-brand-700"
                  disabled={busy}
                  onClick={() => unblock.mutate(entry)}
                >
                  رفع مسدودی
                </Button>
              </div>
            ))
          ) : (
            <p className="rounded-xl border border-dashed border-slate-200 px-4 py-6 text-center text-xs text-slate-400">
              موردی مسدود نشده است.
            </p>
          )}
        </div>
      </article>

      <article className="rounded-2xl border border-slate-200 bg-white p-4">
        <h2 className="text-sm font-bold text-slate-900">خروج اجباری کاربر</h2>
        <p className="mt-1 text-[11px] leading-6 text-slate-500">
          همه توکن‌های دسترسی و تازه‌سازی کاربر باطل می‌شوند و باید دوباره وارد شود.
        </p>
        <form
          className="mt-3 flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (logoutPhone.trim()) forceLogout.mutate();
          }}
        >
          <Input
            value={logoutPhone}
            onChange={(event) => setLogoutPhone(event.target.value)}
            placeholder="۰۹۱۲…"
            dir="ltr"
            className="h-12 w-full flex-1 text-left sm:w-auto"
          />
          <Button type="submit" size="sm" disabled={busy} loading={forceLogout.isPending}>
            خروج اجباری
          </Button>
        </form>
      </article>
    </section>
  );
}

export default AdminSecurityPage;
