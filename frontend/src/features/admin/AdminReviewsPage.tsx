import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";

interface Row { id: string; rating: number; text: string | null; status: string }

export default function AdminReviewsPage() {
  const [items, setItems] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api<{ data: { items: Row[] } }>("/admin/reviews?status=pending")
      .then((r) => setItems(r.data.items))
      .catch((e) => setError(errorMessage(e)));
  }
  useEffect(load, []);

  async function setStatus(id: string, status: string) {
    await api(`/businesses/reviews/${id}/status`, { method: "PATCH", body: JSON.stringify({ status }) });
    load();
  }

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-bold">نظرات در انتظار</h1>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {items.length === 0 && <p className="text-sm text-slate-500">موردی نیست.</p>}
      {items.map((r) => (
        <div key={r.id} className="rounded-2xl border border-slate-200 bg-white p-3">
          <p className="text-sm">⭐ {r.rating}</p>
          <p className="text-sm text-slate-600">{r.text}</p>
          <div className="mt-2 flex gap-2">
            <button className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs text-white" onClick={() => setStatus(r.id, "approved")}>تأیید</button>
            <button className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs text-white" onClick={() => setStatus(r.id, "rejected")}>رد</button>
          </div>
        </div>
      ))}
    </div>
  );
}
