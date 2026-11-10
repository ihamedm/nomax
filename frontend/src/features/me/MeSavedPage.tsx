import { Spinner } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { useApi } from "@/lib/query";
import { BusinessCard } from "@/features/business/BusinessCard";
import type { BusinessListItem } from "@/types";

export default function MeSavedPage() {
  const { data, error, isLoading } = useApi<{ items: BusinessListItem[] }>(
    ["me", "bookmarks"],
    "/me/bookmarks",
  );

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-lg font-black text-slate-900">ذخیره‌شده‌ها</h1>
        <p className="mt-1 text-xs text-slate-500">کسب‌وکارهایی که برای بعد ذخیره کرده‌اید.</p>
      </header>

      {isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}
      {!isLoading && !error && data?.items.length === 0 && (
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <p className="text-sm font-bold text-slate-900">هنوز چیزی ذخیره نکرده‌اید</p>
          <p className="mt-1 text-xs leading-6 text-slate-500">
            در صفحه هر کسب‌وکار، دکمه ذخیره را بزنید تا اینجا نمایش داده شود.
          </p>
        </div>
      )}

      {data && data.items.length > 0 && (
        <div className="grid gap-3 sm:grid-cols-2">
          {data.items.map((business) => (
            <BusinessCard key={business.id} business={business} />
          ))}
        </div>
      )}
    </section>
  );
}
