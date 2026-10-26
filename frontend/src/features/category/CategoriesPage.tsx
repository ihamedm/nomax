import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "@/lib/api";

interface Category {
  id: number;
  slug: string;
  name: string;
  icon: string;
  subcategory_count: number;
}

export default function CategoriesPage() {
  const [items, setItems] = useState<Category[]>([]);
  useEffect(() => {
    api<{ data: { items: Category[] } }>("/categories").then((r) => setItems(r.data.items)).catch(() => {});
  }, []);
  return (
    <main className="mx-auto max-w-xl p-4">
      <h1 className="mb-3 text-xl font-bold">دسته‌بندی‌ها</h1>
      <div className="grid grid-cols-2 gap-2">
        {items.map((c) => (
          <Link key={c.id} to={`/search?cat=${c.slug}`} className="rounded-xl border border-slate-200 p-3">
            <span className="text-2xl">{c.icon}</span>
            <p className="text-sm font-medium">{c.name}</p>
          </Link>
        ))}
      </div>
    </main>
  );
}
