import { Link } from "react-router-dom";

import { Spinner } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { useApi } from "@/lib/query";
import type { Category } from "@/types";

export default function CategoriesPage() {
  const { data, error, isLoading } = useApi<{ items: Category[] }>(["categories"], "/categories");

  return (
    <main className="mx-auto w-full max-w-5xl px-4 py-4">
      <h1 className="mb-3 text-xl font-bold">دسته‌بندی‌ها</h1>
      {isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}
      <div className="grid grid-cols-3 gap-2 sm:gap-3">
        {data?.items.map((c) => (
          <Link key={c.id} to={`/search?cat=${c.slug}`} className="flex min-h-24 flex-col items-center justify-center gap-1.5 rounded-2xl border border-slate-200 bg-white px-2 py-3 text-center">
            <span className="text-2xl">{c.icon}</span>
            <p className="line-clamp-1 text-xs font-bold text-slate-800">{c.name}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
