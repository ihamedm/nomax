import { useEffect, useState } from "react";
import { api, errorMessage } from "@/lib/api";

interface Row { id: string; name: string; status: string; is_verified: boolean; is_24h: boolean }

export default function AdminBusinessesPage() {
  const [items, setItems] = useState<Row[]>([]);
  const [error, setError] = useState<string | null>(null);

  function load() {
    api<{ data: { items: Row[] } }>("/admin/businesses?status=pending")
      .then((r) => setItems(r.data.items))
      .catch((e) => setError(errorMessage(e)));
  }
  useEffect(load, []);

  async function act(id: string, action: "approve" | "reject") {
    await api(`/admin/businesses/${id}/${action}`, {
      method: "PATCH",
      body: JSON.stringify(action === "reject" ? { reason: "نقص مدارک" } : {}),
    });
    load();
  }

  return (
    <div className="space-y-3">
      <h1 className="text-lg font-bold">کسب‌وکارهای در انتظار</h1>
      {error && <p className="text-sm text-rose-600">{error}</p>}
      {items.length === 0 && <p className="text-sm text-slate-500">موردی نیست.</p>}
      {items.map((b) => (
        <div key={b.id} className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-3">
          <div>
            <p className="font-medium">{b.name}</p>
            <p className="text-xs text-slate-500">{b.status}</p>
          </div>
          <div className="flex gap-2">
            <button className="rounded-lg bg-emerald-600 px-3 py-1.5 text-xs text-white" onClick={() => act(b.id, "approve")}>تأیید</button>
            <button className="rounded-lg bg-rose-600 px-3 py-1.5 text-xs text-white" onClick={() => act(b.id, "reject")}>رد</button>
          </div>
        </div>
      ))}
    </div>
  );
}
