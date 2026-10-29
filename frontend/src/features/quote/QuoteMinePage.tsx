import { Link } from "react-router-dom";

import { Spinner } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";

interface Quote {
  id: string;
  title: string;
  status: string;
  is_urgent: boolean;
  created_at?: string | null;
}

export default function QuoteMinePage() {
  const { data, error, isLoading } = useApi<{ items: Quote[] }>(
    ["quotes", "mine"],
    "/quotes/requests/mine",
  );

  return (
    <main className="mx-auto max-w-xl space-y-3 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">درخواست‌های من</h1>
        <Link to="/quote/new" className="text-sm text-brand-600">درخواست جدید</Link>
      </div>
      {isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}
      {!isLoading && !error && data?.items.length === 0 && (
        <p className="text-sm text-slate-500">درخواستی ندارید.</p>
      )}
      {data?.items.map((q) => (
        <div key={q.id} className="rounded-2xl border border-slate-200 p-3">
          <p className="font-medium">{q.title}</p>
          <p className="text-xs text-slate-500">
            {q.status}
            {q.is_urgent ? " · فوری" : ""}
            {q.created_at ? ` · ${formatJalali(q.created_at)}` : ""}
          </p>
        </div>
      ))}
    </main>
  );
}
