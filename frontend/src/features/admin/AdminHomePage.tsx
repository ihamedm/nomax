import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { fa, formatPhone, permissionLabel, ROLE_LABELS } from "@/lib/format";
import { useApi } from "@/lib/query";
import { useAuth } from "@/stores/auth";

const CARDS = [
  {
    to: "/admin/analytics",
    title: "تحلیل و آمار",
    description: "رشد روزانه، قیف استعلام، ترکیب کاربران و تحلیل عرضه و تقاضا.",
    superadminOnly: false,
    permission: "stats.read",
  },
  {
    to: "/admin/businesses",
    title: "کسب‌وکارها",
    description: "بررسی، تأیید یا رد کسب‌وکارهای در انتظار.",
    superadminOnly: false,
    permission: "business.read",
  },
  {
    to: "/admin/reviews",
    title: "نظرات",
    description: "تأیید یا رد نظرات کاربران و محاسبه امتیاز کسب‌وکار.",
    superadminOnly: false,
    permission: "review.read",
  },
  {
    to: "/admin/quotes",
    title: "استعلام‌های قیمت",
    description: "پایش درخواست‌ها، پیشنهادها، نرخ تبدیل و لغو درخواست‌های فعال.",
    superadminOnly: false,
    permission: "quote.read",
  },
  {
    to: "/admin/categories",
    title: "دسته‌بندی‌ها",
    description: "مدیریت دسته‌ها و زیردسته‌های خدمات.",
    superadminOnly: false,
    permission: "category.read",
  },
  {
    to: "/admin/tags",
    title: "برچسب‌ها",
    description: "برچسب‌های خدمت، وضعیت و میزان استفاده.",
    superadminOnly: false,
    permission: "category.read",
  },
  {
    to: "/admin/ads",
    title: "بنرها و تبلیغات",
    description: "مدیریت بنرهای صفحه اصلی و محل نمایش.",
    superadminOnly: false,
    permission: "ad.manage",
  },
  {
    to: "/admin/settings",
    title: "تنظیمات",
    description: "جستجوهای پرطرفدار و تنظیمات محتوایی.",
    superadminOnly: false,
    permission: "admin.settings.manage",
  },
  {
    to: "/admin/files",
    title: "مدیریت فایل‌ها",
    description: "مرور و ساخت یا حذف فایل‌ها و پوشه‌های ArvanCloud S3.",
    superadminOnly: false,
    permission: "storage.manage",
  },
  {
    to: "/admin/data",
    title: "مدل‌های داده",
    description: "دسترسی کامل مدیر کل برای مشاهده و ویرایش جدول‌های پایگاه داده.",
    superadminOnly: true,
    permission: null,
  },
  {
    to: "/admin/users",
    title: "کاربران و دسترسی‌ها",
    description: "ساخت مدیر، تغییر نقش و تعیین دسترسی دقیق هر ماژول.",
    superadminOnly: true,
    permission: null,
  },
  {
    to: "/admin/dev-otps",
    title: "کدهای ورود توسعه",
    description: "کدهای یکبارمصرف فعال برای ورود بدون پیامک (فقط توسعه).",
    superadminOnly: true,
    permission: null,
  },
];

interface Stats {
  pending: number;
  approved: number;
  rejected: number;
  urgent: number;
}

export function AdminHomePage() {
  const user = useAuth((state) => state.user);
  const canReadStats = Boolean(
    user && (user.role === "superadmin" || user.permissions.includes("stats.read")),
  );
  const stats = useApi<Stats>(["admin", "stats"], "/admin/stats/overview", {
    enabled: canReadStats,
  });
  if (!user) return null;

  const cards = CARDS.filter((card) => {
    if (card.superadminOnly && user.role !== "superadmin") return false;
    if (card.permission && user.role !== "superadmin" && !user.permissions.includes(card.permission)) {
      return false;
    }
    return true;
  });

  return (
    <section className="space-y-5">
      <div className="rounded-3xl bg-gradient-to-l from-brand-600 to-brand-500 p-6 text-white">
        <p className="text-xs text-white/70">خوش آمدید</p>
        <h1 className="mt-1 text-xl font-black">{user.full_name || formatPhone(user.phone)}</h1>
        <div className="mt-3 flex items-center gap-2">
          <span className="rounded-full bg-white/15 px-3 py-1 text-xs">
            {ROLE_LABELS[user.role]}
          </span>
          {user.role === "superadmin" ? (
            <Badge tone="brand" className="bg-white/15 text-white">
              دسترسی کامل
            </Badge>
          ) : (
            <Badge tone="amber">{user.permissions.length} دسترسی واگذارشده</Badge>
          )}
        </div>
      </div>

      {canReadStats && stats.data && (
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
          {[
            { label: "در انتظار", value: stats.data.pending, tone: "text-amber-600" },
            { label: "تأییدشده", value: stats.data.approved, tone: "text-emerald-600" },
            { label: "ردشده", value: stats.data.rejected, tone: "text-rose-600" },
            { label: "۲۴ ساعته", value: stats.data.urgent, tone: "text-brand-600" },
          ].map((item) => (
            <div key={item.label} className="rounded-2xl border border-slate-200 bg-white p-3">
              <p className="text-[11px] text-slate-400">{item.label}</p>
              <p className={`mt-1 text-xl font-black ${item.tone}`}>{fa(item.value)}</p>
            </div>
          ))}
        </div>
      )}

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {cards.map((card) => (
          <Link
            key={card.to}
            to={card.to}
            className="group rounded-2xl border border-slate-200 bg-white p-5 transition-colors hover:border-brand-300"
          >
            <p className="text-sm font-bold text-slate-900">{card.title}</p>
            <p className="mt-2 text-xs leading-6 text-slate-500">{card.description}</p>
            <span className="mt-4 inline-block text-xs font-medium text-brand-600">
              ورود به بخش ←
            </span>
          </Link>
        ))}
      </div>

      {user.role !== "superadmin" && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-sm font-bold text-slate-900">دسترسی‌های شما</p>
          {user.permissions.length === 0 ? (
            <p className="mt-2 text-xs leading-6 text-slate-500">
              هنوز دسترسی خاصی به شما واگذار نشده است. از مدیر کل بخواهید دسترسی لازم را
              تنظیم کند.
            </p>
          ) : (
            <ul className="mt-3 flex flex-wrap gap-2">
              {user.permissions.map((code) => (
                <li key={code}>
                  <Badge tone="slate">{permissionLabel(code)}</Badge>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}

      <div className="flex items-center justify-between rounded-2xl border border-slate-200 bg-white p-4">
        <div>
          <p className="text-sm font-medium text-slate-800">مشاهده سایت</p>
          <p className="text-xs text-slate-400">بازگشت به صفحه اصلی نومکس</p>
        </div>
        <Link to="/">
          <Button variant="outline" size="sm">
            صفحه اصلی
          </Button>
        </Link>
      </div>
    </section>
  );
}
