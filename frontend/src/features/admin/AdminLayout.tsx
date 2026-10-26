import { Link, NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";

import { Button, Spinner } from "@/components/ui/button";
import { RoleBadge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import { formatPhone, ROLE_LABELS } from "@/lib/format";
import { isAdmin, useAuth } from "@/stores/auth";

const NAV = [
  { to: "/admin", label: "داشبورد", end: true, superadminOnly: false },
  { to: "/admin/businesses", label: "کسب‌وکارها", end: false, superadminOnly: false },
  { to: "/admin/reviews", label: "نظرات", end: false, superadminOnly: false },
  { to: "/admin/users", label: "کاربران", end: false, superadminOnly: true },
  { to: "/admin/dev-otps", label: "کدهای ورود", end: false, superadminOnly: true },
];

export function AdminLayout() {
  const user = useAuth((state) => state.user);
  const ready = useAuth((state) => state.ready);
  const logout = useAuth((state) => state.logout);
  const navigate = useNavigate();

  if (!ready) {
    return (
      <div className="flex min-h-[100dvh] items-center justify-center text-brand-600">
        <Spinner />
      </div>
    );
  }
  if (!user) return <Navigate to="/login" replace />;
  if (!isAdmin(user)) return <Navigate to="/" replace />;

  return (
    <div className="min-h-[100dvh] bg-slate-50 pb-28">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between gap-3 px-5 py-3">
          <div className="min-w-0">
            <p className="text-[11px] text-slate-400">پنل مدیریت نومکس</p>
            <div className="flex items-center gap-2">
              <p className="truncate text-sm font-bold text-slate-900" dir="ltr">
                {user.full_name || formatPhone(user.phone)}
              </p>
              <RoleBadge role={user.role} label={ROLE_LABELS[user.role]} />
            </div>
          </div>
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
        </div>
      </header>

      <main className="mx-auto w-full max-w-3xl px-5 py-6">
        <Outlet />
      </main>

      <nav className="safe-bottom fixed inset-x-0 bottom-0 z-20 border-t border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-around px-2 pt-2">
          {NAV.filter((item) => !item.superadminOnly || user.role === "superadmin").map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "flex min-w-16 flex-col items-center rounded-xl px-3 py-1.5 text-xs transition-colors",
                  isActive ? "font-bold text-brand-600" : "text-slate-400",
                )
              }
            >
              {({ isActive }) => (
                <>
                  <span
                    className={cn(
                      "mb-1 h-1.5 w-1.5 rounded-full bg-current transition-opacity",
                      isActive ? "opacity-100" : "opacity-0",
                    )}
                  />
                  {item.label}
                </>
              )}
            </NavLink>
          ))}
          <Link
            to="/"
            className="flex min-w-16 flex-col items-center rounded-xl px-3 py-1.5 text-xs text-slate-400"
          >
            <span className="mb-1 h-1.5 w-1.5 rounded-full bg-current opacity-0" />
            سایت
          </Link>
        </div>
      </nav>
    </div>
  );
}
