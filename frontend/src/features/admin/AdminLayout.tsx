import { useEffect, useState } from "react";
import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Button, Spinner } from "@/components/ui/button";
import { RoleBadge } from "@/components/ui/badge";
import { Icon, MoonIcon, SunIcon } from "@/components/ui/icons";
import { loginPath, returnPath } from "@/lib/auth-redirect";
import { cn } from "@/lib/cn";
import { formatPhone, ROLE_LABELS } from "@/lib/format";
import { isAdmin, useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";

const NAV = [
  { to: "/admin", label: "داشبورد", icon: "▦", end: true, superadminOnly: false, permission: null },
  { to: "/admin/analytics", label: "تحلیل و آمار", icon: "◔", end: false, superadminOnly: false, permission: "stats.read" },
  { to: "/admin/businesses", label: "کسب‌وکارها", icon: "⌂", end: false, superadminOnly: false, permission: "business.read" },
  { to: "/admin/reviews", label: "نظرات", icon: "★", end: false, superadminOnly: false, permission: "review.read" },
  { to: "/admin/quotes", label: "استعلام‌ها", icon: "⌕", end: false, superadminOnly: false, permission: "quote.read" },
  { to: "/admin/notifications", label: "پیام‌ها و اطلاعیه‌ها", icon: "✉", end: false, superadminOnly: false, permission: "notification.manage" },
  { to: "/admin/categories", label: "دسته‌بندی‌ها", icon: "☰", end: false, superadminOnly: false, permission: "category.read" },
  { to: "/admin/tags", label: "برچسب‌ها", icon: "#", end: false, superadminOnly: false, permission: "category.read" },
  { to: "/admin/ads", label: "بنرها و تبلیغات", icon: "▣", end: false, superadminOnly: false, permission: "ad.manage" },
  { to: "/admin/settings", label: "تنظیمات", icon: "⚙", end: false, superadminOnly: false, permission: "admin.settings.manage" },
  { to: "/admin/files", label: "مدیریت فایل‌ها", icon: "▤", end: false, superadminOnly: false, permission: "storage.manage" },
  { to: "/admin/data", label: "مدل‌های داده", icon: "⛁", end: false, superadminOnly: true, permission: null },
  { to: "/admin/backups", label: "پشتیبان‌گیری", icon: "▤", end: false, superadminOnly: true, permission: null },
  { to: "/admin/cache", label: "کش‌ها", icon: "⚡", end: false, superadminOnly: false, permission: "admin.settings.manage" },
  { to: "/admin/users", label: "کاربران و دسترسی‌ها", icon: "☷", end: false, superadminOnly: true, permission: null },
  { to: "/admin/security", label: "امنیت و محدودیت‌ها", icon: "⛨", end: false, superadminOnly: true, permission: null },
];

export function AdminLayout() {
  const user = useAuth((state) => state.user);
  const ready = useAuth((state) => state.ready);
  const logout = useAuth((state) => state.logout);
  const theme = useTheme((state) => state.theme);
  const toggleTheme = useTheme((state) => state.toggleTheme);
  const navigate = useNavigate();
  const location = useLocation();
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    setNavOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (!navOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setNavOpen(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [navOpen]);

  if (!ready) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center text-brand-600">
        <Spinner />
      </div>
    );
  }
  if (!user) return <Navigate to={loginPath(returnPath(location))} replace />;
  if (!isAdmin(user)) return <Navigate to="/" replace />;

  const navItems = NAV.filter((item) => {
    if (item.superadminOnly && user.role !== "superadmin") return false;
    if (item.permission && user.role !== "superadmin" && !user.permissions.includes(item.permission)) {
      return false;
    }
    return true;
  });
  const current =
    navItems.find((item) =>
      item.end ? location.pathname === item.to : location.pathname.startsWith(item.to),
    ) ?? navItems[0];

  return (
    <div className="admin-shell flex h-[100dvh] w-full overflow-hidden bg-slate-100">
      {navOpen && (
        <button
          type="button"
          aria-label="بستن منو"
          onClick={() => setNavOpen(false)}
          className="fixed inset-0 z-30 bg-slate-900/40 backdrop-blur-[1px] lg:hidden"
        />
      )}

      <aside
        id="admin-nav"
        className={cn(
          "fixed inset-y-0 right-0 z-40 flex w-72 max-w-[85vw] flex-col border-l border-slate-200 bg-white transition-transform duration-200",
          navOpen ? "translate-x-0" : "translate-x-full",
          "lg:static lg:z-auto lg:w-60 lg:max-w-none lg:shrink-0 lg:translate-x-0",
        )}
      >
        <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-slate-100 px-4">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-600 text-xs font-black text-white">
            N
          </span>
          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-black text-slate-900">پنل مدیریت نومکس</p>
            <p className="text-[11px] text-slate-400">مدیریت بازار محلی</p>
          </div>
          <button
            type="button"
            onClick={() => setNavOpen(false)}
            aria-label="بستن منو"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-xl text-slate-500 transition-colors hover:bg-slate-50 lg:hidden"
          >
            <Icon className="h-4 w-4">
              <path d="M6 6l12 12M18 6 6 18" />
            </Icon>
          </button>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setNavOpen(false)}
              className={({ isActive }) =>
                cn(
                  "flex items-center gap-2.5 rounded-xl px-2.5 py-2 text-[13px] transition-colors",
                  isActive
                    ? "bg-brand-50 font-bold text-brand-700"
                    : "text-slate-600 hover:bg-slate-50 hover:text-slate-900",
                )
              }
            >
              <span className="w-4 text-center text-sm" aria-hidden>
                {item.icon}
              </span>
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 shrink-0 items-center justify-between gap-2 border-b border-slate-200 bg-white px-3 sm:px-4 lg:gap-3 lg:px-5">
          <div className="flex min-w-0 items-center gap-2">
            <button
              type="button"
              onClick={() => setNavOpen(true)}
              aria-label="باز کردن منو"
              aria-expanded={navOpen}
              aria-controls="admin-nav"
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 lg:hidden"
            >
              <Icon className="h-5 w-5">
                <path d="M4 6h16M4 12h16M4 18h16" />
              </Icon>
            </button>
            <div className="min-w-0">
              <p className="text-[10px] text-slate-400">مدیریت</p>
              <h1 className="truncate text-sm font-black text-slate-900">{current?.label}</h1>
            </div>
          </div>
          <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
            <Link
              to="/"
              className="hidden h-9 items-center rounded-xl border border-slate-200 px-3 text-xs font-medium text-slate-600 transition-colors hover:bg-slate-50 hover:text-slate-900 sm:inline-flex"
            >
              مشاهده سایت
            </Link>
            <Button
              size="sm"
              variant="ghost"
              onClick={async () => {
                await logout();
                navigate("/login", { replace: true });
              }}
            >
              خروج
            </Button>
            <span className="mx-1 hidden h-6 w-px bg-slate-200 lg:block" aria-hidden />
            <div className="hidden text-xs font-bold text-slate-800 lg:block">
              <p className="max-w-40 truncate">{user.full_name || formatPhone(user.phone)}</p>
            </div>
            <span className="hidden sm:inline-flex">
              <RoleBadge role={user.role} label={ROLE_LABELS[user.role]} />
            </span>
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "تغییر به حالت روشن" : "تغییر به حالت تاریک"}
              className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-900"
            >
              {theme === "dark" ? (
                <SunIcon className="h-4 w-4 text-amber-500" />
              ) : (
                <MoonIcon className="h-4 w-4" />
              )}
            </button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto p-3 sm:p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
