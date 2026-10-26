import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { formatPhone, permissionLabel, ROLE_LABELS } from "@/lib/format";
import { useAuth } from "@/stores/auth";

const CARDS = [
  {
    to: "/admin/users",
    title: "کاربران و دسترسی‌ها",
    description: "تغییر نقش، ساخت مدیر و تعیین دسترسی‌های دقیق هر مدیر.",
    superadminOnly: true,
  },
  {
    to: "/admin/dev-otps",
    title: "کدهای ورود توسعه",
    description: "کدهای یکبارمصرف فعال برای ورود بدون پیامک (فقط توسعه).",
    superadminOnly: true,
  },
];

export function AdminHomePage() {
  const user = useAuth((state) => state.user);
  if (!user) return null;

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

      {user.role === "superadmin" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {CARDS.map((card) => (
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
      ) : (
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

      <div className="rounded-2xl border border-dashed border-slate-300 bg-white/60 p-5 text-xs leading-6 text-slate-500">
        بخش‌های تأیید کسب‌وکار، نظرات، دسته‌بندی‌ها و گزارش رویدادها در فازهای بعدی به
        همین پنل اضافه می‌شوند. ساختار دسترسی‌ها از همین حالا آماده است.
      </div>

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
