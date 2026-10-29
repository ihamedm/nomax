import { Link, useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useUnreadNotificationCount } from "@/features/notifications/useUnreadNotifications";
import { useOwnerReviewBadge } from "@/features/reviews/useOwnerReviewBadge";
import { formatPhone, ROLE_LABELS } from "@/lib/format";
import { isAdmin, useAuth } from "@/stores/auth";

interface ProfileLink {
  to: string;
  title: string;
  description: string;
  ownerOnly?: boolean;
}

const LINKS: ProfileLink[] = [
  { to: "/me/businesses", title: "کسب‌وکارهای من", description: "مدیریت کسب‌وکارهای ثبت‌شده" },
  { to: "/me/customers", title: "مشتریان", description: "درخواست‌های قیمت دریافتی از مشتریان" },
  { to: "/me/quotes", title: "درخواست‌های من", description: "وضعیت درخواست‌های قیمت شما" },
  { to: "/me/saved", title: "ذخیره‌شده‌ها", description: "کسب‌وکارهای نشان‌شده برای بعد" },
  { to: "/me/notifications", title: "اعلان‌ها", description: "پیام‌ها و اطلاع‌رسانی‌های حساب" },
  { to: "/me/reviews", title: "نظرات", description: "نظرات تأییدشده و خصوصی کسب‌وکارهای شما", ownerOnly: true },
  { to: "/me/analytics", title: "آمار کسب‌وکار", description: "امتیاز و تعداد نظرات تأییدشده" },
  { to: "/businesses/new", title: "ثبت کسب‌وکار جدید", description: "افزودن کسب‌وکار به نومکس" },
];

export default function MeHomePage() {
  const navigate = useNavigate();
  const user = useAuth((state) => state.user);
  const logout = useAuth((state) => state.logout);
  const unreadCount = useUnreadNotificationCount();
  const reviewBadgeCount = useOwnerReviewBadge();
  if (!user) return null;
  const isOwner = user.role === "owner";
  const links = LINKS.filter((item) => !item.ownerOnly || isOwner);

  async function handleLogout() {
    await logout();
    navigate("/", { replace: true });
  }

  return (
    <section className="space-y-4">
      <div className="rounded-3xl bg-gradient-to-l from-brand-600 to-brand-500 p-6 text-white">
        <p className="text-xs text-white/70">پروفایل شما</p>
        <h1 className="mt-1 text-xl font-black">{user.full_name || "کاربر نومکس"}</h1>
        <p className="mt-2 text-sm text-white/90" dir="ltr">
          {formatPhone(user.phone)}
        </p>
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <span className="rounded-full bg-white/15 px-3 py-1 text-xs">{ROLE_LABELS[user.role]}</span>
          <Badge tone="slate" className="bg-white/15 text-white">
            {user.is_phone_verified ? "شماره تأییدشده" : "شماره تأییدنشده"}
          </Badge>
          {isAdmin(user) && (
            <Link to="/admin" className="text-xs underline underline-offset-4">
              ورود به پنل مدیریت
            </Link>
          )}
        </div>
      </div>

      <div className="grid gap-3 sm:grid-cols-2">
        {links.map((item) => (
          <Link
            key={item.to}
            to={item.to}
            className="rounded-2xl border border-slate-200 bg-white p-4 transition-colors hover:border-brand-300"
          >
            <div className="flex items-start justify-between gap-2">
              <p className="text-sm font-bold text-slate-900">{item.title}</p>
              {item.to === "/me/notifications" && unreadCount > 0 && (
                <Badge tone="rose">
                  {unreadCount.toLocaleString("fa-IR")} پیام خوانده‌نشده
                </Badge>
              )}
              {item.to === "/me/reviews" && reviewBadgeCount > 0 && (
                <Badge tone="amber">
                  {reviewBadgeCount.toLocaleString("fa-IR")} نظر جدید
                </Badge>
              )}
            </div>
            <p className="mt-1 text-xs leading-6 text-slate-500">{item.description}</p>
          </Link>
        ))}
      </div>

      <div className="border-t border-slate-200 pt-4">
        <Button variant="outline" className="w-full" onClick={() => void handleLogout()}>
          خروج از حساب
        </Button>
      </div>
    </section>
  );
}
