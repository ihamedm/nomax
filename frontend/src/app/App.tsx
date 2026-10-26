import { useEffect } from "react";
import { Link, Route, Routes } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { AdminHomePage } from "@/features/admin/AdminHomePage";
import { AdminLayout } from "@/features/admin/AdminLayout";
import { AdminUsersPage } from "@/features/admin/AdminUsersPage";
import { DevOtpsPage } from "@/features/admin/DevOtpsPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { BusinessDetailPage } from "@/features/business/BusinessDetailPage";
import { SearchPage } from "@/features/business/SearchPage";
import CreateBusinessPage from "@/features/business/CreateBusinessPage";
import OwnerPage from "@/features/owner/OwnerPage";
import StaticPage from "@/features/static/StaticPage";
import CategoriesPage from "@/features/category/CategoriesPage";
import QuoteNewPage from "@/features/quote/QuoteNewPage";
import QuoteMinePage from "@/features/quote/QuoteMinePage";
import AdminBusinessesPage from "@/features/admin/AdminBusinessesPage";
import AdminReviewsPage from "@/features/admin/AdminReviewsPage";
import { HomePage } from "@/features/home/HomePage";
import { useAuth } from "@/stores/auth";

function SessionBootstrap() {
  const ready = useAuth((state) => state.ready);
  const hydrate = useAuth((state) => state.hydrate);

  useEffect(() => {
    if (!ready) void hydrate();
  }, [ready, hydrate]);

  useEffect(() => {
    const onExpired = () => useAuth.setState({ user: null, ready: true });
    window.addEventListener("nomax:session-expired", onExpired);
    return () => window.removeEventListener("nomax:session-expired", onExpired);
  }, []);

  return null;
}

function NotFoundPage() {
  return (
    <main className="flex min-h-[100dvh] flex-col items-center justify-center gap-4 bg-slate-50 px-6 text-center">
      <p className="text-5xl font-black text-brand-600">۴۰۴</p>
      <h1 className="text-lg font-bold text-slate-900">این صفحه پیدا نشد</h1>
      <p className="max-w-sm text-sm leading-6 text-slate-500">
        ممکن است نشانی را اشتباه وارد کرده باشید یا این بخش هنوز ساخته نشده باشد.
      </p>
      <Link to="/">
        <Button>بازگشت به خانه</Button>
      </Link>
    </main>
  );
}

export function App() {
  return (
    <>
      <SessionBootstrap />
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/search" element={<SearchPage />} />
        <Route path="/categories" element={<CategoriesPage />} />
        <Route path="/quote/new" element={<QuoteNewPage />} />
        <Route path="/quote/mine" element={<QuoteMinePage />} />
        <Route path="/businesses/new" element={<CreateBusinessPage />} />
        <Route path="/businesses/:slug" element={<BusinessDetailPage />} />
        <Route path="/owner" element={<OwnerPage />} />
        <Route path="/login" element={<LoginPage />} />
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<AdminHomePage />} />
          <Route path="businesses" element={<AdminBusinessesPage />} />
          <Route path="reviews" element={<AdminReviewsPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="dev-otps" element={<DevOtpsPage />} />
        </Route>
        <Route path="/pages/:page" element={<StaticPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </>
  );
}
