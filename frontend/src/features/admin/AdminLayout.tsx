import { useEffect } from "react";
import { Link, NavLink, Navigate, Outlet, useNavigate } from "react-router-dom";

import { Button, Spinner } from "@/components/ui/button";
import { cn } from "@/lib/cn";
import { formatPhone } from "@/lib/format";
import { isAdmin, useAuth } from "@/stores/auth";

const NAV = [
  { to: "/admin/users", label: "کاربران", superadminOnly: true },
  { to: "/admin/dev-otps", label: "کدهای ورود", superadminOnly: true },
];

export function AdminLayout() {
  const user = useAuth((state) => state.user);
  const ready = useAuth((state) => state.ready);
  const hydrate = useAuth((state) => state.hydrate);
  const logout = useAuth((state) => state.logout);
  const navigate = useNavigate();

  useEffect(() => {
    if (!ready) void hydrate();
  }, [ready, hydrate]);

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
    <div className="min-h-[100dvh] bg-slate-50 pb-24">
      <header className="sticky top-0 z-20 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex w-full max-w-3xl items-center justify-between px-5 py-3">
          <div>
            <p className="text-[11px] text-slate-400">پنل مدیریت نومکس</p>
            <p className="text-sm font-bold text-slate-900" dir="ltr">
              {formatPhone(user.phone)}
            </p>
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
              className={({ isActive }) =>
                cn(
                  "flex min-w-24 flex-col items-center rounded-xl px-3 py-1.5 text-xs",
                  isActive ? "text-brand-600" : "text-slate-400",
                )
              }
            >
              <span
                className={cn(
                  "mb-1 h-1.5 w-1.5 rounded-full",
                  "bg-current opacity-0",
                  "aria-[current=page]:opacity-100",
                )}
              />
              {item.label}
            </NavLink>
          ))}
          <Link
            to="/"
            className="flex min-w-24 flex-col items-center rounded-xl px-3 py-1.5 text-xs text-slate-400"
          >
            <span className="mb-1 h-1.5 w-1.5 rounded-full bg-current opacity-0" />
            سایت
          </Link>
        </div>
      </nav>
    </div>
  );
}
