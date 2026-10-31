import { lazy, Suspense, useEffect } from "react";
import { Link, Navigate, Route, Routes } from "react-router-dom";

import { Button, Spinner } from "@/components/ui/button";
import { AppLayout } from "@/app/AppLayout";
import { AdminHomePage } from "@/features/admin/AdminHomePage";
import { AdminLayout } from "@/features/admin/AdminLayout";
import { AdminUsersPage } from "@/features/admin/AdminUsersPage";
import { DevOtpsPage } from "@/features/admin/DevOtpsPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { RequireAuth } from "@/features/auth/RequireAuth";
import { BusinessDetailPage } from "@/features/business/BusinessDetailPage";
import { SearchPage } from "@/features/business/SearchPage";
import CreateBusinessPage from "@/features/business/CreateBusinessPage";
import { MeLayout } from "@/features/me/MeLayout";
import MeHomePage from "@/features/me/MeHomePage";
import MeBusinessesPage from "@/features/me/MeBusinessesPage";
import MeBusinessEditPage from "@/features/me/MeBusinessEditPage";
import MeNotificationsPage from "@/features/me/MeNotificationsPage";
import MeReviewsPage from "@/features/me/MeReviewsPage";
import MeAnalyticsPage from "@/features/me/MeAnalyticsPage";
import MeQuotesPage from "@/features/me/MeQuotesPage";
import MeCustomersPage from "@/features/me/MeCustomersPage";
import MeSavedPage from "@/features/me/MeSavedPage";
import StaticPage from "@/features/static/StaticPage";
import CategoriesPage from "@/features/category/CategoriesPage";
import QuoteNewPage from "@/features/quote/QuoteNewPage";
import QuoteMinePage from "@/features/quote/QuoteMinePage";
import QuoteDetailPage from "@/features/quote/QuoteDetailPage";
import AdminBusinessesPage from "@/features/admin/AdminBusinessesPage";
import AdminReviewsPage from "@/features/admin/AdminReviewsPage";
import AdminCategoriesPage from "@/features/admin/AdminCategoriesPage";
import AdminTagsPage from "@/features/admin/AdminTagsPage";
import AdminAdsPage from "@/features/admin/AdminAdsPage";
import AdminSettingsPage from "@/features/admin/AdminSettingsPage";
import AdminDataPage from "@/features/admin/AdminDataPage";
import AdminFilesPage from "@/features/admin/AdminFilesPage";
import AdminNotificationsPage from "@/features/admin/AdminNotificationsPage";
import AdminQuotesPage from "@/features/admin/AdminQuotesPage";
import { HomePage } from "@/features/home/HomePage";
import { useAuth } from "@/stores/auth";

const AdminAnalyticsPage = lazy(
  () => import("@/features/admin/AdminAnalyticsPage"),
);

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
        <Route element={<AppLayout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/search" element={<SearchPage />} />
          <Route path="/categories" element={<CategoriesPage />} />
          <Route path="/quote" element={<Navigate to="/quote/mine" replace />} />
          <Route
            path="/quote/new"
            element={
              <RequireAuth>
                <QuoteNewPage />
              </RequireAuth>
            }
          />
          <Route
            path="/quote/mine"
            element={
              <RequireAuth>
                <QuoteMinePage />
              </RequireAuth>
            }
          />
          <Route
            path="/quote/mine/:id"
            element={
              <RequireAuth>
                <QuoteDetailPage />
              </RequireAuth>
            }
          />
          <Route
            path="/businesses/new"
            element={
              <RequireAuth>
                <CreateBusinessPage />
              </RequireAuth>
            }
          />
          <Route
            path="/businesses/:id/edit"
            element={
              <RequireAuth>
                <MeBusinessEditPage />
              </RequireAuth>
            }
          />
          <Route path="/businesses/:slug" element={<BusinessDetailPage />} />
          <Route path="/me" element={<MeLayout />}>
            <Route index element={<MeHomePage />} />
            <Route path="businesses" element={<MeBusinessesPage />} />
            <Route path="notifications" element={<MeNotificationsPage />} />
            <Route path="reviews" element={<MeReviewsPage />} />
            <Route path="analytics" element={<MeAnalyticsPage />} />
            <Route path="quotes" element={<MeQuotesPage />} />
            <Route path="customers" element={<MeCustomersPage />} />
            <Route path="saved" element={<MeSavedPage />} />
          </Route>
          <Route path="/owner" element={<Navigate to="/me" replace />} />
          <Route path="/pages/:page" element={<StaticPage />} />
        </Route>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/admin" element={<AdminLayout />}>
          <Route index element={<AdminHomePage />} />
          <Route path="businesses" element={<AdminBusinessesPage />} />
          <Route path="notifications" element={<AdminNotificationsPage />} />
          <Route path="reviews" element={<AdminReviewsPage />} />
          <Route path="quotes" element={<AdminQuotesPage />} />
          <Route
            path="analytics"
            element={
              <Suspense
                fallback={
                  <div className="flex min-h-[40dvh] items-center justify-center text-brand-600">
                    <Spinner />
                  </div>
                }
              >
                <AdminAnalyticsPage />
              </Suspense>
            }
          />
          <Route path="categories" element={<AdminCategoriesPage />} />
          <Route path="tags" element={<AdminTagsPage />} />
          <Route path="ads" element={<AdminAdsPage />} />
          <Route path="settings" element={<AdminSettingsPage />} />
          <Route path="data" element={<AdminDataPage />} />
          <Route path="files" element={<AdminFilesPage />} />
          <Route path="users" element={<AdminUsersPage />} />
          <Route path="dev-otps" element={<DevOtpsPage />} />
        </Route>
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </>
  );
}
