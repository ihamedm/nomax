import { useCallback, useEffect, useState, type FormEvent } from "react";
import { Link, useNavigate } from "react-router-dom";

import { RoleBadge } from "@/components/ui/badge";
import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button, Spinner } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { toFa } from "@/lib/digits";
import { formatPhone, ROLE_LABELS } from "@/lib/format";
import { isAdmin, useAuth } from "@/stores/auth";
import type { Category, Subcategory } from "@/types";

export function HomePage() {
  const navigate = useNavigate();
  const user = useAuth((state) => state.user);
  const logout = useAuth((state) => state.logout);

  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchTerm, setSearchTerm] = useState("");

  const [activeCategory, setActiveCategory] = useState<Category | null>(null);
  const [subcategories, setSubcategories] = useState<Record<number, Subcategory[]>>({});
  const [subLoading, setSubLoading] = useState(false);

  const loadCategories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await api<{ items: Category[] }>("/categories");
      setCategories(result.items);
    } catch (loadError) {
      setError(errorMessage(loadError));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCategories();
  }, [loadCategories]);

  function submitSearch(event: FormEvent) {
    event.preventDefault();
    const term = searchTerm.trim();
    navigate(term ? `/search?q=${encodeURIComponent(term)}` : "/search");
  }

  async function openCategory(category: Category) {
    setActiveCategory(category);
    if (subcategories[category.id]) return;
    setSubLoading(true);
    try {
      const result = await api<{ items: Subcategory[] }>(
        `/categories/${category.id}/subcategories`,
      );
      setSubcategories((current) => ({ ...current, [category.id]: result.items }));
    } catch (loadError) {
      setActiveCategory(null);
      setError(errorMessage(loadError));
    } finally {
      setSubLoading(false);
    }
  }

  const activeSubcategories = activeCategory ? subcategories[activeCategory.id] : undefined;

  return (
    <main className="mx-auto flex min-h-[100dvh] w-full max-w-xl flex-col px-5 py-8">
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="text-xs text-slate-400">نومکس</p>
          <h1 className="text-xl font-black text-slate-900">بازار محلی بهبهان</h1>
        </div>
        {user && <RoleBadge role={user.role} label={ROLE_LABELS[user.role]} />}
      </header>

      <section className="mt-6 rounded-3xl bg-gradient-to-l from-brand-600 to-brand-500 p-6 text-white">
        <h2 className="text-lg font-bold">چه خدمتی لازم دارید؟</h2>
        <p className="mt-2 text-sm leading-6 text-white/85">
          بین کسب‌وکارهای تأییدشده بهبهان جستجو کنید؛ نزدیک‌ترین‌ها را ببینید و امتیاز و
          موقعیت هرکدام را مقایسه کنید.
        </p>
        <form onSubmit={submitSearch} className="mt-4 flex gap-2">
          <Input
            value={searchTerm}
            onChange={(event) => setSearchTerm(event.target.value)}
            placeholder="جستجوی کسب‌وکار، خدمت یا دسته…"
            aria-label="جستجوی کسب‌وکار"
            enterKeyHint="search"
            className="border-white/20 bg-white/15 text-white placeholder:text-white/60 focus:border-white focus:ring-white/30"
          />
          <Button type="submit" className="shrink-0 bg-white text-brand-700 hover:bg-white/90">
            جستجو
          </Button>
        </form>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link
            to="/search?sort=nearest"
            className="rounded-full bg-white/15 px-3 py-1 text-[11px] text-white/90"
          >
            نزدیک‌ترین‌ها
          </Link>
          <Link
            to="/search?sort=urgent"
            className="rounded-full bg-white/15 px-3 py-1 text-[11px] text-white/90"
          >
            خدمات ۲۴ ساعته
          </Link>
          <Link
            to="/search?sort=top"
            className="rounded-full bg-white/15 px-3 py-1 text-[11px] text-white/90"
          >
            بهترین امتیازها
          </Link>
        </div>
      </section>

      <section className="mt-6">
        <div className="mb-3 flex items-center justify-between">
          <h2 className="text-sm font-bold text-slate-800">دسته‌بندی‌ها</h2>
          {!loading && !error && (
            <Link to="/search" className="text-[11px] text-brand-600">
              همه کسب‌وکارها ←
            </Link>
          )}
        </div>

        {loading && (
          <div className="flex justify-center py-12 text-brand-600">
            <Spinner />
          </div>
        )}

        {!loading && error && (
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
            <p>{error}</p>
            <Button size="sm" variant="outline" className="mt-3" onClick={() => void loadCategories()}>
              تلاش دوباره
            </Button>
          </div>
        )}

        {!loading && !error && (
          <div className="grid grid-cols-2 gap-3">
            {categories.map((category) => (
              <button
                key={category.id}
                type="button"
                onClick={() => void openCategory(category)}
                className="flex min-h-24 flex-col items-start gap-2 rounded-2xl border border-slate-200 bg-white p-4 text-right transition-colors hover:border-brand-300 active:bg-brand-50"
              >
                <span className="text-2xl" aria-hidden>
                  {category.icon}
                </span>
                <span className="text-sm font-bold text-slate-900">{category.name}</span>
                <span className="text-[11px] text-slate-400">
                  {toFa(category.subcategory_count)} زیردسته
                </span>
              </button>
            ))}
          </div>
        )}
      </section>

      {user ? (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">حساب شما</p>
          <p className="mt-1 text-lg font-bold text-slate-900" dir="ltr">
            {formatPhone(user.phone)}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {user.is_phone_verified ? "شماره تأیید شده" : "شماره تأیید نشده"}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {isAdmin(user) && (
              <Link to="/admin">
                <Button size="sm">ورود به پنل مدیریت</Button>
              </Link>
            )}
            <Button size="sm" variant="outline" onClick={() => void logout()}>
              خروج
            </Button>
          </div>
        </section>
      ) : (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-600">برای استفاده از نومکس وارد شوید.</p>
          <Link to="/login" className="mt-4 inline-block">
            <Button>ورود / ثبت‌نام</Button>
          </Link>
        </section>
      )}

      <p className="mt-6 text-center text-[11px] leading-6 text-slate-400">
        فاز ۲: جستجوی جغرافیایی، فهرست و صفحه کسب‌وکار، نقشه نشان
      </p>

      <BottomSheet
        open={activeCategory !== null}
        title={activeCategory ? `${activeCategory.icon} ${activeCategory.name}` : ""}
        onClose={() => setActiveCategory(null)}
      >
        {subLoading && (
          <div className="flex justify-center py-8 text-brand-600">
            <Spinner />
          </div>
        )}

        {!subLoading && activeSubcategories && activeSubcategories.length === 0 && (
          <p className="py-6 text-center text-sm text-slate-500">
            برای این دسته زیردسته‌ای ثبت نشده است.
          </p>
        )}

        {!subLoading && activeSubcategories && activeSubcategories.length > 0 && activeCategory && (
          <div className="space-y-4">
            <p className="text-xs leading-6 text-slate-500">
              یک زیردسته انتخاب کنید تا کسب‌وکارهای همان خدمت را ببینید.
            </p>
            <div className="grid grid-cols-2 gap-2">
              <Link
                to={`/search?cat=${activeCategory.slug}`}
                onClick={() => setActiveCategory(null)}
                className="rounded-xl border border-brand-200 bg-brand-50 px-3 py-3 text-sm font-medium text-brand-700"
              >
                همه {activeCategory.name}
              </Link>
              {activeSubcategories.map((subcategory) => (
                <Link
                  key={subcategory.id}
                  to={`/search?cat=${activeCategory.slug}&subcat=${subcategory.slug}`}
                  onClick={() => setActiveCategory(null)}
                  className="rounded-xl border border-slate-200 bg-slate-50 px-3 py-3"
                >
                  <span className="text-lg" aria-hidden>
                    {subcategory.icon}
                  </span>
                  <p className="mt-1 text-sm font-medium text-slate-800">{subcategory.name}</p>
                  {subcategory.standard_tags.length > 0 && (
                    <p className="mt-1 text-[10px] text-slate-400">
                      {toFa(subcategory.standard_tags.length)} برچسب خدمت
                    </p>
                  )}
                </Link>
              ))}
            </div>
          </div>
        )}
      </BottomSheet>
    </main>
  );
}
