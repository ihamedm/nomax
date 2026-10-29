import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, NavLink, Outlet, useLocation, useNavigate } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { SearchIcon, SunIcon, MoonIcon } from "@/components/ui/icons";
import { UnreadBadge } from "@/features/notifications/UnreadBadge";
import { useUnreadNotificationCount } from "@/features/notifications/useUnreadNotifications";
import { useOwnerReviewBadge } from "@/features/reviews/useOwnerReviewBadge";
import { cn } from "@/lib/cn";
import { formatPhone, ROLE_LABELS } from "@/lib/format";
import { isAdmin, useAuth } from "@/stores/auth";
import { useTheme } from "@/stores/theme";

function Icon({ children }: { children: ReactNode }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      {children}
    </svg>
  );
}

const HomeIcon = () => (
  <Icon>
    <path d="M3 10.5 12 3l9 7.5" />
    <path d="M5 9.5V21h14V9.5" />
  </Icon>
);
const GridIcon = () => (
  <Icon>
    <rect x="3" y="3" width="7" height="7" rx="1.5" />
    <rect x="14" y="3" width="7" height="7" rx="1.5" />
    <rect x="3" y="14" width="7" height="7" rx="1.5" />
    <rect x="14" y="14" width="7" height="7" rx="1.5" />
  </Icon>
);
const QuoteIcon = () => (
  <Icon>
    <path d="M12 5v14M5 12h14" />
    <rect x="3" y="3" width="18" height="18" rx="5" />
  </Icon>
);
const UserIcon = () => (
  <Icon>
    <circle cx="12" cy="8" r="4" />
    <path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" />
  </Icon>
);
const BusinessIcon = () => (
  <Icon>
    <rect x="3" y="7" width="18" height="14" rx="2" />
    <path d="M8 7V5a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2M3 12h18" />
  </Icon>
);
const CustomersIcon = () => (
  <Icon>
    <circle cx="9" cy="8" r="3.5" />
    <path d="M2.5 21c0-3.5 2.9-5.5 6.5-5.5s6.5 2 6.5 5.5" />
    <path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18 15.7c2.1.7 3.5 2.4 3.5 5.3" />
  </Icon>
);
const QuotesIcon = () => (
  <Icon>
    <path d="M6 3h9l4 4v14H6z" />
    <path d="M14 3v5h5M9 12h6M9 16h6" />
  </Icon>
);
const BookmarkIcon = () => (
  <Icon>
    <path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5V21l-6-4-6 4z" />
  </Icon>
);

const BOTTOM_NAV = [
  { to: "/", label: "خانه", icon: HomeIcon, end: true },
  { to: "/categories", label: "دسته‌ها", icon: GridIcon, end: false },
  { to: "/search", label: "جستجو", icon: SearchIcon, end: false },
  { to: "/quote/new", label: "درخواست", icon: QuoteIcon, end: false },
  { to: "/me", label: "حساب", icon: UserIcon, end: false },
];

const ACCOUNT_BOTTOM_NAV = [
  { to: "/", label: "خانه", icon: HomeIcon, end: true },
  { to: "/me/businesses", label: "کسب‌وکار من", icon: BusinessIcon, end: false },
  { to: "/me/customers", label: "مشتریان", icon: CustomersIcon, end: false },
  { to: "/me/quotes", label: "درخواست‌ها", icon: QuotesIcon, end: false },
  { to: "/me/saved", label: "ذخیره‌شده", icon: BookmarkIcon, end: false },
];

const DRAWER_LINKS = [
  { to: "/", label: "خانه" },
  { to: "/categories", label: "دسته‌بندی‌ها" },
  { to: "/search", label: "جستجو" },
  { to: "/quote/new", label: "درخواست قیمت" },
  { to: "/me/quotes", label: "درخواست‌های من" },
  { to: "/me", label: "حساب کاربری" },
  { to: "/me/notifications", label: "اعلان‌ها" },
  { to: "/me/businesses", label: "کسب‌وکارهای من" },
  { to: "/me/customers", label: "مشتریان" },
  { to: "/me/saved", label: "ذخیره‌شده‌ها" },
];

export function AppLayout() {
  const location = useLocation();
  const navigate = useNavigate();
  const user = useAuth((state) => state.user);
  const logout = useAuth((state) => state.logout);
  const theme = useTheme((state) => state.theme);
  const toggleTheme = useTheme((state) => state.toggleTheme);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const drawerRef = useRef<HTMLDivElement | null>(null);
  const unreadCount = useUnreadNotificationCount();
  const reviewBadgeCount = useOwnerReviewBadge();
  const badgeCount = unreadCount + reviewBadgeCount;

  const isHome = location.pathname === "/";
  const isAccount = location.pathname === "/me" || location.pathname.startsWith("/me/");
  const isBusinessWizard =
    location.pathname === "/businesses/new" ||
    /^\/businesses\/[^/]+\/edit$/.test(location.pathname);
  const bottomItems = isAccount ? ACCOUNT_BOTTOM_NAV : BOTTOM_NAV;

  useEffect(() => {
    setDrawerOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    const node = drawerRef.current;
    if (!node) return;
    // Keep the closed drawer out of the tab order while it stays mounted for
    // its slide-out transition.
    if (drawerOpen) node.removeAttribute("inert");
    else node.setAttribute("inert", "");
  }, [drawerOpen]);

  useEffect(() => {
    if (!drawerOpen) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key === "Escape") setDrawerOpen(false);
    };
    const previous = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    window.addEventListener("keydown", onKey);
    return () => {
      document.body.style.overflow = previous;
      window.removeEventListener("keydown", onKey);
    };
  }, [drawerOpen]);

  return (
    <div
      className={cn(
        "min-h-[100dvh] bg-slate-50",
        isBusinessWizard ? "pb-0" : "pb-24 md:pb-0",
      )}
    >
      <header className="sticky top-0 z-30 border-b border-slate-200 bg-white/95 backdrop-blur">
        <div className="mx-auto flex h-14 w-full max-w-5xl items-center justify-between gap-3 px-4">
          <div className="flex items-center gap-2">
            {isHome ? (
              <button
                type="button"
                aria-label="باز کردن منو"
                aria-expanded={drawerOpen}
                onClick={() => setDrawerOpen(true)}
                className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-600 hover:bg-slate-100"
              >
                <Icon>
                  <path d="M4 6h16M4 12h16M4 18h10" />
                </Icon>
              </button>
            ) : (
              <button
                type="button"
                aria-label="بازگشت"
                onClick={() => (window.history.length > 1 ? navigate(-1) : navigate("/"))}
                className="flex h-10 w-10 items-center justify-center rounded-xl text-slate-600 hover:bg-slate-100"
              >
                <Icon>
                  <path d="M9 5l7 7-7 7" />
                </Icon>
              </button>
            )}
            <Link to="/" className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-600 text-sm font-black text-white">
                N
              </span>
              <span className="text-base font-black tracking-tight text-slate-900">نومکس</span>
            </Link>
          </div>

          <Link
            to={user ? "/me" : "/login"}
            aria-label={
              user
                ? badgeCount > 0
                  ? `حساب کاربری، ${badgeCount.toLocaleString("fa-IR")} مورد خوانده‌نشده`
                  : "حساب کاربری"
                : "ورود"
            }
            className="relative flex h-10 w-10 items-center justify-center rounded-full border border-slate-200 bg-white text-slate-600 hover:border-brand-300 hover:text-brand-600"
          >
            <UserIcon />
            <UnreadBadge count={badgeCount} />
          </Link>
        </div>
      </header>

      <Outlet />

      {!isBusinessWizard && (
        <nav className="fixed inset-x-4 bottom-4 z-30 md:hidden">
          <div className="mx-auto flex max-w-md items-center justify-around rounded-2xl border border-slate-200 bg-white/95 px-2 py-2 shadow-xl shadow-slate-900/10 backdrop-blur">
            {bottomItems.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "flex min-w-14 flex-col items-center gap-1 rounded-xl px-2 py-1 text-[10px]",
                    isActive ? "text-brand-600" : "text-slate-400",
                  )
                }
              >
                <item.icon />
                <span>{item.label}</span>
              </NavLink>
            ))}
          </div>
        </nav>
      )}

      <div
        ref={drawerRef}
        className={cn(
          "fixed inset-0 z-40 transition-opacity duration-300",
          drawerOpen ? "opacity-100" : "pointer-events-none opacity-0",
        )}
        role="dialog"
        aria-modal={drawerOpen}
        aria-label="منوی اصلی"
        aria-hidden={!drawerOpen}
      >
        <button
          type="button"
          aria-label="بستن منو"
          tabIndex={drawerOpen ? 0 : -1}
          className="absolute inset-0 bg-slate-900/40 backdrop-blur-[2px]"
          onClick={() => setDrawerOpen(false)}
        />
        <aside
          className={cn(
            "absolute inset-y-0 right-0 flex w-72 max-w-[85vw] flex-col bg-white shadow-2xl transition-transform duration-300 ease-out will-change-transform",
            drawerOpen ? "translate-x-0" : "translate-x-full",
          )}
        >
          <div className="flex items-center justify-between border-b border-slate-100 px-4 py-4">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-600 text-sm font-black text-white">
                N
              </span>
              <span className="text-sm font-black text-slate-900">نومکس</span>
            </div>
            <button
              type="button"
              onClick={() => setDrawerOpen(false)}
              className="text-sm text-slate-400"
            >
              بستن
            </button>
          </div>

          <div className="border-b border-slate-100 px-4 py-3">
            {user ? (
              <>
                <p className="text-sm font-bold text-slate-900">
                  {user.full_name || formatPhone(user.phone)}
                </p>
                <p className="mt-0.5 text-[11px] text-slate-400">{ROLE_LABELS[user.role]}</p>
              </>
            ) : (
              <Link
                to="/login"
                onClick={() => setDrawerOpen(false)}
                className="text-sm font-bold text-brand-600"
              >
                ورود / ثبت‌نام
              </Link>
            )}
          </div>

          <nav className="flex-1 space-y-1 overflow-y-auto px-3 py-3">
            {DRAWER_LINKS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.to === "/"}
                onClick={() => setDrawerOpen(false)}
                className={({ isActive }) =>
                  cn(
                    "block rounded-xl px-3 py-2.5 text-sm",
                    isActive
                      ? "bg-brand-50 font-bold text-brand-700"
                      : "text-slate-600 hover:bg-slate-50",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
            {user && isAdmin(user) && (
              <Link
                to="/admin"
                onClick={() => setDrawerOpen(false)}
                className="block rounded-xl bg-slate-900 px-3 py-2.5 text-sm font-bold text-white"
              >
                پنل مدیریت
              </Link>
            )}
          </nav>

          <div className="space-y-2 border-t border-slate-100 p-3">
            <button
              type="button"
              onClick={toggleTheme}
              aria-label={theme === "dark" ? "تغییر به حالت روشن" : "تغییر به حالت تاریک"}
              className="flex w-full items-center justify-between rounded-xl px-3 py-2.5 text-sm text-slate-600 transition-colors hover:bg-slate-50"
            >
              <span className="flex items-center gap-2">
                {theme === "dark" ? (
                  <SunIcon className="h-5 w-5 text-amber-500" />
                ) : (
                  <MoonIcon className="h-5 w-5" />
                )}
                {theme === "dark" ? "حالت روشن" : "حالت تاریک"}
              </span>
              <span
                className={cn(
                  "flex h-6 w-11 items-center rounded-full p-0.5 transition-colors",
                  theme === "dark" ? "justify-start bg-brand-600" : "justify-end bg-slate-200",
                )}
              >
                <span className="h-5 w-5 rounded-full bg-white shadow theme-switch-knob" />
              </span>
            </button>

            {user && (
              <Button
                variant="outline"
                className="w-full"
                onClick={async () => {
                  setDrawerOpen(false);
                  await logout();
                  navigate("/", { replace: true });
                }}
              >
                خروج
              </Button>
            )}
          </div>
        </aside>
      </div>
    </div>
  );
}
