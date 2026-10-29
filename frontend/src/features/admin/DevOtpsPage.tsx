import { useEffect, useState } from "react";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { errorMessage } from "@/lib/api";
import { fa, formatPhone } from "@/lib/format";
import { useApi } from "@/lib/query";
import type { DevOtp } from "@/types";

const OTP_TTL_SECONDS = 120;
const REFRESH_INTERVAL_MS = 5000;

export function DevOtpsPage() {
  const toast = useToast();
  const { data, isLoading, error: queryError, refetch, dataUpdatedAt } = useApi<{ items: DevOtp[] }>(
    ["admin", "dev-otps"],
    "/admin/dev/otps",
    { refetchInterval: REFRESH_INTERVAL_MS },
  );
  const items = data?.items ?? [];
  const updatedAt = dataUpdatedAt || Date.now();
  const [now, setNow] = useState(() => Date.now());
  const loading = isLoading;
  const error = queryError ? errorMessage(queryError) : null;

  useEffect(() => {
    const interval = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(interval);
  }, []);

  function remainingSeconds(item: DevOtp): number {
    const elapsed = Math.floor((now - updatedAt) / 1000);
    return Math.max(0, item.ttl_seconds - elapsed);
  }

  async function copyCode(item: DevOtp) {
    try {
      await navigator.clipboard.writeText(item.otp);
      toast(`کد ${fa(item.otp)} کپی شد.`);
    } catch {
      toast("کپی خودکار ممکن نشد؛ کد را دستی وارد کنید.");
    }
  }

  return (
    <section className="space-y-4">
      <header className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">کدهای ورود توسعه</h1>
          <p className="mt-1 text-xs leading-6 text-slate-500">
            کدهای فعالِ درخواست‌شده در محیط توسعه. این صفحه در محیط تولید اصلاً وجود ندارد.
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={() => void refetch()} disabled={loading}>
          به‌روزرسانی
        </Button>
      </header>

      {loading && items.length === 0 && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}

      {error && (
        <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
          <p>{error}</p>
          <Button size="sm" variant="outline" className="mt-3" onClick={() => void refetch()}>
            تلاش دوباره
          </Button>
        </div>
      )}

      {!loading && !error && items.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-2xl">📵</p>
          <p className="mt-3 text-sm font-bold text-slate-900">کد فعالی وجود ندارد</p>
          <p className="mt-1 text-xs leading-6 text-slate-500">
            در صفحه ورود شماره‌ای وارد کنید تا کد آزمایشی ساخته شود. کدها دو دقیقه اعتبار
            دارند.
          </p>
        </div>
      )}

      {items.length > 0 && (
        <div className="grid gap-3 md:grid-cols-2 2xl:grid-cols-3">
          {items.map((item) => {
            const remaining = remainingSeconds(item);
            const expired = remaining <= 0;
            const progress = Math.min(100, (remaining / OTP_TTL_SECONDS) * 100);

            return (
              <article
                key={item.phone}
                className="rounded-2xl border border-slate-200 bg-white p-4"
              >
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-sm font-bold text-slate-900" dir="ltr">
                      {formatPhone(item.phone)}
                    </p>
                    <p className="mt-1 text-[11px] text-slate-400">
                      {expired ? "منقضی شده" : `${fa(remaining)} ثانیه باقی‌مانده`}
                    </p>
                  </div>
                  <Badge tone={expired ? "rose" : "brand"}>
                    {expired ? "منقضی" : "فعال"}
                  </Badge>
                </div>

                <div className="mt-3 flex items-center gap-3">
                  <p
                    className="flex-1 rounded-xl bg-slate-900 py-3 text-center text-xl font-bold tracking-[0.5em] text-white"
                    dir="ltr"
                  >
                    {item.otp}
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={expired}
                    onClick={() => void copyCode(item)}
                  >
                    کپی
                  </Button>
                </div>

                <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-slate-100">
                  <div
                    className="h-full rounded-full bg-brand-500 transition-[width] duration-1000"
                    style={{ width: `${progress}%` }}
                  />
                </div>
              </article>
            );
          })}
        </div>
      )}

      <p className="rounded-xl bg-amber-50 px-4 py-3 text-[11px] leading-6 text-amber-700">
        این کدها فقط برای ورود در محیط توسعه‌اند. هرگز کلید «DEV_OTP_ENABLED» را در محیط
        تولید روشن نکنید؛ مسیر این صفحه در تولید حتی ثبت نمی‌شود.
      </p>
    </section>
  );
}
