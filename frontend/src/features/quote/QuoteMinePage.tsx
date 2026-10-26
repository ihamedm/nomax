import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "@/lib/api";

interface Quote {
  id: string;
  title: string;
  status: string;
  is_urgent: boolean;
}

export default function QuoteMinePage() {
  const [items, setItems] = useState<Quote[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ data: { items: Quote[] } }>("/quotes/requests/mine")
      .then((r) => setItems(r.data.items))
      .catch((e) => setError(errorMessage(e)));
  }, []);

  return (
    <main className="mx-auto max-w-xl space-y-3 p-4">
      <div className="flex items-center justify-between">
        <h1 className="text-xl font-bold">درخواست‌های من</h1>
        <Link to="/quote/new" className="text-sm text-brand-600">درخواست جدید</Link>
      </div>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {items.length === 0 && <p className="text-sm text-slate-500">درخواستی ندارید.</p>}
      {items.map((q) => (
        <div key={q.id} className="rounded-2xl border border-slate-200 p-3">
          <p className="font-medium">{q.title}</p>
          <p className="text-xs text-slate-500">{q.status}{q.is_urgent ? " · فوری" : ""}</p>
        </div>
      ))}
    </main>
  );
}
