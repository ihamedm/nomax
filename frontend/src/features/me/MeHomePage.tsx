import type { ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { Icon } from "@/components/ui/icons";
import { useUnreadNotificationCount } from "@/features/notifications/useUnreadNotifications";
import { useOwnerReviewBadge } from "@/features/reviews/useOwnerReviewBadge";
import { isActiveQuote } from "@/features/quote/quote-utils";
import type { IncomingResponse, Quote } from "@/features/quote/types";
import { fa, formatPhone, ROLE_LABELS } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";
import { isAdmin, useAuth } from "@/stores/auth";
import type { BusinessListItem } from "@/types";

interface BusinessList {
  items: BusinessListItem[];
  limit: number;
  can_create: boolean;
}

interface DashboardRowProps {
  to?: string;
  title: string;
  description: string;
  icon: ReactNode;
  badge?: { label: string; tone: "brand" | "amber" | "rose" };
  onClick?: () => void;
}

function StoreIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M4 10v10h16V10M3 10l2-6h14l2 6" />
      <path d="M3 10a3 3 0 0 0 6 0 3 3 0 0 0 6 0 3 3 0 0 0 6 0M9 20v-5h6v5" />
    </Icon>
  );
}

function UsersIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <circle cx="9" cy="8" r="3.5" />
      <path d="M2.5 21c0-3.5 2.9-5.5 6.5-5.5s6.5 2 6.5 5.5" />
      <path d="M16 4.8a3.5 3.5 0 0 1 0 6.4M18 15.7c2.1.7 3.5 2.4 3.5 5.3" />
    </Icon>
  );
}

function ReceiptIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M6 3h12v18l-2-1.5L14 21l-2-1.5L10 21l-2-1.5L6 21z" />
      <path d="M9 8h6M9 12h6M9 16h4" />
    </Icon>
  );
}

function BookmarkIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5V21l-6-4-6 4z" />
    </Icon>
  );
}

function ChartIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M4 20V10M10 20V4M16 20v-7M22 20H2" />
    </Icon>
  );
}

function StarIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="m12 3 2.7 5.5 6.1.9-4.4 4.3 1 6.1-5.4-2.9-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z" />
    </Icon>
  );
}

function BellIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M18 9a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9" />
      <path d="M10.5 21a2 2 0 0 0 3 0" />
    </Icon>
  );
}

function PlusIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M12 5v14M5 12h14" />
    </Icon>
  );
}

function LogoutIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4M16 17l5-5-5-5M21 12H9" />
    </Icon>
  );
}

function AdminIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M12 3 4.5 6v5c0 4.5 3.2 8.2 7.5 10 4.3-1.8 7.5-5.5 7.5-10V6L12 3Z" />
      <path d="m9 12 2 2 4-4" />
    </Icon>
  );
}

function ChevronIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M15 5 8 12l7 7" />
    </Icon>
  );
}

const BADGE_TONES = {
  brand: "bg-brand-50 text-brand-700",
  amber: "bg-amber-50 text-amber-700",
  rose: "bg-rose-50 text-rose-600",
};

function DashboardRow({ to, title, description, icon, badge, onClick }: DashboardRowProps) {
  const content = (
    <>
      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-slate-50 text-slate-500 transition group-hover:bg-brand-50 group-hover:text-brand-600">
        {icon}
      </span>
      <span className="min-w-0 flex-1">
        <span className="flex min-w-0 items-center gap-2">
          <span className="truncate text-[13px] font-bold text-slate-800">{title}</span>
          {badge && (
            <span
              className={`shrink-0 rounded-full px-2 py-0.5 text-[9px] font-bold ${BADGE_TONES[badge.tone]}`}
            >
              {badge.label}
            </span>
          )}
        </span>
        <span className="mt-0.5 block truncate text-[10px] text-slate-400">{description}</span>
      </span>
      <ChevronIcon className="h-4 w-4 shrink-0 text-slate-300 transition-transform group-hover:-translate-x-0.5" />
    </>
  );

  const className =
    "group flex items-center gap-3 rounded-2xl px-3 py-3 transition-colors hover:bg-slate-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-brand-500/30";

  if (to) {
    return (
      <Link to={to} className={className}>
        {content}
      </Link>
    );
  }

  return (
    <button type="button" onClick={onClick} className={`${className} w-full text-right`}>
      {content}
    </button>
  );
}

function GroupLabel({ children }: { children: ReactNode }) {
  return (
    <p className="px-3 pb-1 pt-2 text-[10px] font-bold tracking-wide text-slate-400">{children}</p>
  );
}

export default function MeHomePage() {
  const navigate = useNavigate();
  const user = useAuth((state) => state.user);
  const logout = useAuth((state) => state.logout);
  const unreadCount = useUnreadNotificationCount();
  const reviewBadgeCount = useOwnerReviewBadge();

  const isOwner = user?.role === "owner";
  const businesses = useApi<BusinessList>(["me", "businesses"], "/me/businesses", {
    enabled: Boolean(user),
  });
  const bookmarks = useApi<{ items: BusinessListItem[] }>(["me", "bookmarks"], "/me/bookmarks", {
    enabled: Boolean(user),
  });
  const quotes = useApi<{ items: Quote[] }>(["quotes", "mine"], "/quotes/requests/mine", {
    enabled: Boolean(user),
  });
  const incoming = useApi<IncomingResponse>(
    ["quotes", "incoming", "new"],
    "/quotes/requests/incoming?scope=new",
    { enabled: Boolean(user) && isOwner },
  );

  if (!user) return null;

  const displayName = user.full_name?.trim() || "کاربر نومکس";
  const initial = Array.from(displayName)[0] || "ن";
  const businessCount = businesses.data ? businesses.data.items.length : null;
  const activeQuoteCount = quotes.data
    ? quotes.data.items.filter((quote) => isActiveQuote(quote)).length
    : null;
  const savedCount = bookmarks.data ? bookmarks.data.items.length : null;
  const pendingBusinesses =
    businesses.data?.items.filter((business) => business.status === "pending").length ?? 0;
  const newIncoming = incoming.data?.counts.new ?? 0;
  const canCreate = businesses.data?.can_create ?? true;
  const showBusinessTools = businessCount === null || businessCount > 0;

  async function handleLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  function countLabel(value: number | null) {
    return value === null ? "…" : fa(value);
  }

  return (
    <section className="mx-auto w-full max-w-4xl py-1 sm:py-3">
      <div className="overflow-hidden rounded-[28px] border border-slate-200/80 bg-white shadow-[0_24px_70px_-50px_rgba(15,23,42,0.55)] md:grid md:grid-cols-[290px_minmax(0,1fr)]">
        <aside className="relative overflow-hidden bg-gradient-to-br from-slate-900 via-slate-900 to-emerald-950 p-5 text-white md:p-6">
          <span
            aria-hidden
            className="absolute -right-14 -top-20 h-52 w-52 rounded-full bg-brand-400/20 blur-3xl"
          />
          <span
            aria-hidden
            className="absolute -bottom-24 -left-16 h-48 w-48 rounded-full bg-emerald-300/10 blur-3xl"
          />

          <div className="relative flex h-full flex-col">
            <div className="flex items-center gap-3.5">
              <span className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl border border-white/15 bg-white/10 text-xl font-black text-brand-100 backdrop-blur">
                {initial}
              </span>
              <div className="min-w-0">
                <p className="text-[10px] font-medium text-white/45">حساب من</p>
                <h1 className="mt-0.5 truncate text-xl font-black leading-7">{displayName}</h1>
                <p dir="ltr" className="mt-0.5 text-[11px] font-medium text-white/55">
                  {formatPhone(user.phone)}
                </p>
              </div>
            </div>

            <div className="mt-4 flex flex-wrap items-center gap-1.5">
              <span className="rounded-full border border-white/10 bg-white/[0.07] px-2.5 py-1 text-[10px] font-medium text-white/75">
                {ROLE_LABELS[user.role]}
              </span>
              <span className="inline-flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.07] px-2.5 py-1 text-[10px] font-medium text-white/75">
                <span
                  className={`h-1.5 w-1.5 rounded-full ${
                    user.is_phone_verified ? "bg-emerald-400" : "bg-amber-300"
                  }`}
                />
                {user.is_phone_verified ? "شماره تأییدشده" : "شماره تأییدنشده"}
              </span>
              {isAdmin(user) && (
                <Link
                  to="/admin"
                  className="inline-flex items-center gap-1 rounded-full border border-brand-300/25 bg-brand-400/15 px-2.5 py-1 text-[10px] font-bold text-brand-100 transition hover:bg-brand-400/25"
                >
                  <AdminIcon className="h-3 w-3" />
                  پنل مدیریت
                </Link>
              )}
            </div>

            <dl className="mt-5 grid grid-cols-3 divide-x divide-x-reverse divide-white/10 border-y border-white/10 py-4">
              <div className="px-1 text-center">
                <dt className="text-[9px] text-white/40">کسب‌وکار</dt>
                <dd className="mt-1 text-lg font-black text-white">{countLabel(businessCount)}</dd>
              </div>
              <div className="px-1 text-center">
                <dt className="text-[9px] text-white/40">درخواست فعال</dt>
                <dd className="mt-1 text-lg font-black text-white">
                  {countLabel(activeQuoteCount)}
                </dd>
              </div>
              <div className="px-1 text-center">
                <dt className="text-[9px] text-white/40">ذخیره‌شده</dt>
                <dd className="mt-1 text-lg font-black text-white">{countLabel(savedCount)}</dd>
              </div>
            </dl>

            {user.created_at && (
              <p className="mt-3 text-[10px] leading-5 text-white/30">
                عضو نومکس از {formatJalali(user.created_at)}
              </p>
            )}

            <div className="mt-4 border-t border-white/10 pt-4 md:mt-auto">
              <p className="text-[10px] leading-5 text-white/35">
                بازار محلی کسب‌وکارها و خدمات بهبهان
              </p>
            </div>
          </div>
        </aside>

        <div className="min-w-0 p-2 sm:p-3">
          <nav aria-label="دسترسی‌های حساب">
            <GroupLabel>کسب‌وکار</GroupLabel>
            <div>
              <DashboardRow
                to="/me/businesses"
                title="کسب‌وکارهای من"
                description="مدیریت و ویرایش کسب‌وکارهای ثبت‌شده"
                icon={<StoreIcon className="h-[18px] w-[18px]" />}
                badge={
                  pendingBusinesses > 0
                    ? { label: `${fa(pendingBusinesses)} در انتظار`, tone: "amber" }
                    : undefined
                }
              />
              {isOwner && (
                <DashboardRow
                  to="/me/customers"
                  title="مشتریان"
                  description="درخواست‌های قیمت دریافتی و پیشنهادهای شما"
                  icon={<UsersIcon className="h-[18px] w-[18px]" />}
                  badge={
                    newIncoming > 0
                      ? { label: `${fa(newIncoming)} جدید`, tone: "rose" }
                      : undefined
                  }
                />
              )}
              {showBusinessTools && (
                <DashboardRow
                  to="/me/analytics"
                  title="آمار کسب‌وکار"
                  description="امتیاز، نظرات تأییدشده و وضعیت مجوز"
                  icon={<ChartIcon className="h-[18px] w-[18px]" />}
                />
              )}
              {isOwner && (
                <DashboardRow
                  to="/me/reviews"
                  title="نظرات"
                  description="نظرات تأییدشده و خصوصی کسب‌وکارهای شما"
                  icon={<StarIcon className="h-[18px] w-[18px]" />}
                  badge={
                    reviewBadgeCount > 0
                      ? { label: `${fa(reviewBadgeCount)} جدید`, tone: "amber" }
                      : undefined
                  }
                />
              )}
              {canCreate && (
                <DashboardRow
                  to="/businesses/new"
                  title="ثبت کسب‌وکار جدید"
                  description="کسب‌وکار خود را به نومکس اضافه کنید"
                  icon={<PlusIcon className="h-[18px] w-[18px]" />}
                />
              )}
            </div>

            <div className="mt-3 border-t border-slate-100 pt-1">
              <GroupLabel>فعالیت و حساب</GroupLabel>
              <DashboardRow
                to="/me/quotes"
                title="درخواست‌های من"
                description="وضعیت درخواست‌های قیمت و پیشنهادهای دریافتی"
                icon={<ReceiptIcon className="h-[18px] w-[18px]" />}
              />
              <DashboardRow
                to="/me/saved"
                title="ذخیره‌شده‌ها"
                description="کسب‌وکارهای نشان‌شده برای بعد"
                icon={<BookmarkIcon className="h-[18px] w-[18px]" />}
              />
              <DashboardRow
                to="/me/notifications"
                title="اعلان‌ها"
                description="پیام‌ها و اطلاع‌رسانی‌های حساب"
                icon={<BellIcon className="h-[18px] w-[18px]" />}
                badge={
                  unreadCount > 0
                    ? { label: `${fa(unreadCount)} خوانده‌نشده`, tone: "rose" }
                    : undefined
                }
              />
              <DashboardRow
                title="خروج از حساب"
                description="پایان دادن به این نشست"
                icon={<LogoutIcon className="h-[18px] w-[18px]" />}
                onClick={() => void handleLogout()}
              />
            </div>
          </nav>
        </div>
      </div>
    </section>
  );
}
