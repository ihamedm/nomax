import { Link, NavLink, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Button, Spinner } from "@/components/ui/button";
import { RoleBadge } from "@/components/ui/badge";
import { MoonIcon, SunIcon } from "@/components/ui/icons";
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
  { to: "/admin/users", label: "کاربران و دسترسی‌ها", icon: "☷", end: false, superadminOnly: true, permission: null },
  { to: "/admin/dev-otps", label: "کدهای ورود", icon: "⌘", end: false, superadminOnly: true, permission: null },
];

export function AdminLayout() {
  const user = useAuth((state) => state.user);
  const ready = useAuth((state) => state.ready);
  const logout = useAuth((state) => state.logout);
  const theme = useTheme((state) => state.theme);
  const toggleTheme = useTheme((state) => state.toggleTheme);
  const navigate = useNavigate();
  const location = useLocation();

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
      <aside className="flex w-60 shrink-0 flex-col border-l border-slate-200 bg-white">
        <div className="flex h-14 shrink-0 items-center gap-2.5 border-b border-slate-100 px-4">
          <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-600 text-xs font-black text-white">
            N
          </span>
          <div className="min-w-0">
            <p className="truncate text-sm font-black text-slate-900">پنل مدیریت نومکس</p>
            <p className="text-[11px] text-slate-400">مدیریت بازار محلی</p>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 py-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
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
        <header className="flex h-14 shrink-0 items-center justify-between gap-3 border-b border-slate-200 bg-white px-4 lg:px-5">
          <div>
            <p className="text-[10px] text-slate-400">مدیریت</p>
            <h1 className="text-sm font-black text-slate-900">{current?.label}</h1>
          </div>
          <div className="flex items-center gap-2">
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
            <span className="mx-1 h-6 w-px bg-slate-200" aria-hidden />
            <div className="hidden text-xs font-bold text-slate-800 lg:block">
              <p className="max-w-40 truncate">{user.full_name || formatPhone(user.phone)}</p>
            </div>
            <RoleBadge role={user.role} label={ROLE_LABELS[user.role]} />
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "تغییر به حالت روشن" : "تغییر به حالت تاریک"}
              className="flex h-9 w-9 items-center justify-center rounded-xl border border-slate-200 text-slate-500 transition-colors hover:bg-slate-50 hover:text-slate-900"
            >
              {theme === "dark" ? (
                <SunIcon className="h-4 w-4 text-amber-500" />
              ) : (
                <MoonIcon className="h-4 w-4" />
              )}
            </button>
          </div>
        </header>

        <main className="min-h-0 flex-1 overflow-y-auto p-4 lg:p-6">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
