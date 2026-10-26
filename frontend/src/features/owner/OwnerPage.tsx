import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "@/lib/api";

interface NotificationItem {
  id: string;
  title: string;
  body: string;
  is_read: boolean;
}

export default function OwnerPage() {
  const [items, setItems] = useState<NotificationItem[]>([]);
  const [businesses, setBusinesses] = useState<{ id: string; name: string; slug: string }[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api<{ data: { items: NotificationItem[] } }>("/notifications")
      .then((r) => setItems(r.data.items))
      .catch((e) => setError(errorMessage(e)));
    api<{ data: { items: { id: string; name: string; slug: string }[] } }>("/me/businesses")
      .then((r) => setBusinesses(r.data.items))
      .catch(() => {});
  }, []);

  return (
    <main className="mx-auto max-w-xl p-4 space-y-3">
      <h1 className="text-xl font-bold">پنل کسب‌وکار</h1>
      <Link to="/businesses/new" className="block text-brand-600 text-sm">ثبت کسب‌وکار جدید</Link>
      {businesses.map((b) => (
        <Link key={b.id} to={`/businesses/${b.slug}`} className="block rounded-2xl border border-slate-200 p-3 text-sm font-medium">
          {b.name}
        </Link>
      ))}
      {error && <p className="text-rose-600 text-sm">{error}</p>}
      {items.length === 0 && <p className="text-slate-500 text-sm">اعلانی ندارید.</p>}
      {items.map((n) => (
        <div key={n.id} className="rounded-2xl border border-slate-200 p-3">
          <p className="font-medium">{n.title}</p>
          <p className="text-sm text-slate-600">{n.body}</p>
        </div>
      ))}
    </main>
  );
}
