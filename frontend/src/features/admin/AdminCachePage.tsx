import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { fa } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";

interface CacheEntry {
  ready: boolean;
  generated_at?: string | null;
  points?: number;
  categories?: number;
  subcategories?: number;
  counts?: Record<string, number>;
  detail_zoom?: number;
}

interface CacheStatus {
  map: CacheEntry;
  catalog: CacheEntry;
}

type CacheName = "map" | "catalog" | "all";

const CARDS: Array<{
  name: Exclude<CacheName, "all">;
  title: string;
  description: string;
  readyLabel: string;
  emptyLabel: string;
  stats: (entry: CacheEntry) => Array<{ label: string; value: string }>;
}> = [
  {
    name: "map",
    title: "نقشه و خوشه‌بندی",
    description:
      "موقعیت کسب‌وکارهای تأییدشده و خوشه‌های آماده برای هر سطح زوم. صفحه نقشه به‌جای پرس‌وجوی مستقیم از این داده می‌خواند.",
    readyLabel: "ساخته‌شده",
    emptyLabel: "خالی",
    stats: (entry) => [
      { label: "کسب‌وکار روی نقشه", value: fa(entry.points ?? 0) },
      { label: "زوم جزئیات", value: fa(entry.detail_zoom ?? 15) },
      {
        label: "سطوح خوشه",
        value: fa(Object.keys(entry.counts ?? {}).length),
      },
    ],
  },
  {
    name: "catalog",
    title: "دسته‌بندی‌ها",
    description:
      "فهرست دسته‌ها و زیردسته‌هایی که در جستجو، فیلترها و فرم ثبت کسب‌وکار استفاده می‌شود.",
    readyLabel: "ساخته‌شده",
    emptyLabel: "خالی",
    stats: (entry) => [
      { label: "دسته‌بندی", value: fa(entry.categories ?? 0) },
      { label: "زیردسته", value: fa(entry.subcategories ?? 0) },
    ],
  },
];

export function AdminCachePage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const statusQuery = useApi<CacheStatus>(["admin", "cache"], "/admin/cache");

  const status = statusQuery.data;

  function invalidate() {
    void queryClient.invalidateQueries({ queryKey: ["admin", "cache"] });
    // Public consumers read the same Redis keys.
    void queryClient.invalidateQueries({ queryKey: ["map"] });
    void queryClient.invalidateQueries({ queryKey: ["categories"] });
    void queryClient.invalidateQueries({ queryKey: ["subcategories"] });
  }

  const rebuild = useMutation({
    mutationFn: (name: CacheName) => api(`/admin/cache/${name}/rebuild`, { method: "POST" }),
    onSuccess: async (_data, name) => {
      toast(name === "all" ? "همه کش‌ها بازسازی شد." : "کش بازسازی شد.");
      invalidate();
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const flush = useMutation({
    mutationFn: (name: CacheName) => api(`/admin/cache/${name}/flush`, { method: "POST" }),
    onSuccess: async (_data, name) => {
      toast(
        name === "all"
          ? "همه کش‌ها پاک شدند؛ در اولین درخواست دوباره ساخته می‌شوند."
          : "کش پاک شد؛ در اولین درخواست دوباره ساخته می‌شود.",
      );
      invalidate();
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const busy = rebuild.isPending || flush.isPending;
  const loading = statusQuery.isLoading;
  const error = statusQuery.error ? errorMessage(statusQuery.error) : null;

  return (
    <section className="space-y-4">
      <header className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">کش‌ها</h1>
          <p className="mt-1 max-w-2xl text-xs leading-6 text-slate-500">
            داده‌های پرمصرف در Redis نگهداری می‌شوند تا نقشه و دسته‌بندی‌ها سریع بارگذاری
            شوند. پس از تأیید یا رد کسب‌وکار، کارگر به‌صورت خودکار کش نقشه را تازه می‌کند؛
            از این صفحه می‌توانید وضعیت را ببینید و دستی بازسازی یا پاک کنید.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            variant="outline"
            disabled={busy || loading}
            onClick={() => void statusQuery.refetch()}
          >
            به‌روزرسانی وضعیت
          </Button>
          <Button size="sm" disabled={busy} onClick={() => rebuild.mutate("all")}>
            بازسازی همه
          </Button>
        </div>
      </header>

      {error && <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">{error}</p>}

      <div className="grid gap-3 lg:grid-cols-2">
        {CARDS.map((card) => {
          const entry = status?.[card.name];
          const ready = Boolean(entry?.ready);
          return (
            <article
              key={card.name}
              className="flex flex-col rounded-2xl border border-slate-200 bg-white p-4"
            >
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm font-bold text-slate-900">{card.title}</h2>
                  <p className="mt-1 text-[11px] leading-6 text-slate-500">{card.description}</p>
                </div>
                <Badge tone={ready ? "brand" : "slate"}>
                  {loading ? "…" : ready ? card.readyLabel : card.emptyLabel}
                </Badge>
              </div>

              <dl className="mt-4 grid grid-cols-3 gap-2">
                {card.stats(entry ?? { ready: false }).map((stat) => (
                  <div key={stat.label} className="rounded-xl bg-slate-50 px-2 py-2 text-center">
                    <dd className="text-base font-black text-slate-900">{stat.value}</dd>
                    <dt className="mt-0.5 text-[10px] text-slate-500">{stat.label}</dt>
                  </div>
                ))}
              </dl>

              <p className="mt-3 text-[11px] text-slate-500">
                آخرین ساخت:{" "}
                {entry?.generated_at ? formatJalali(entry.generated_at) : "هنوز ساخته نشده"}
              </p>

              <div className="mt-auto flex flex-wrap gap-2 pt-4">
                <Button
                  size="sm"
                  disabled={busy}
                  loading={rebuild.isPending && rebuild.variables === card.name}
                  onClick={() => rebuild.mutate(card.name)}
                >
                  بازسازی
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy || !ready}
                  loading={flush.isPending && flush.variables === card.name}
                  onClick={() => flush.mutate(card.name)}
                >
                  پاک کردن
                </Button>
              </div>
            </article>
          );
        })}
      </div>

      <p className="rounded-xl border border-dashed border-slate-300 bg-white px-4 py-3 text-[11px] leading-6 text-slate-500">
        پاک کردن کش خطرناک نیست: در اولین درخواست عمومی، داده به‌صورت خودکار از پایگاه داده
        بازسازی می‌شود. بازسازی دستی زمانی مفید است که بخواهید تغییرات را بی‌درنگ روی نقشه
        ببینید.
      </p>
    </section>
  );
}

export default AdminCachePage;
