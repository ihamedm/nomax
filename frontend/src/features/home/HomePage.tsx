import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { RoleBadge } from "@/components/ui/badge";
import { formatPhone, ROLE_LABELS } from "@/lib/format";
import { isAdmin, useAuth } from "@/stores/auth";

export function HomePage() {
  const user = useAuth((state) => state.user);
  const logout = useAuth((state) => state.logout);

  return (
    <main className="mx-auto flex min-h-[100dvh] w-full max-w-xl flex-col px-5 py-8">
      <header className="flex items-center justify-between">
        <div>
          <p className="text-xs text-slate-400">نومکس</p>
          <h1 className="text-xl font-black text-slate-900">بازار محلی بهبهان</h1>
        </div>
        {user && <RoleBadge role={user.role} label={ROLE_LABELS[user.role]} />}
      </header>

      <section className="mt-8 rounded-3xl bg-gradient-to-l from-brand-600 to-brand-500 p-6 text-white">
        <h2 className="text-lg font-bold">فاز ۱ فعال است</h2>
        <p className="mt-2 text-sm leading-6 text-white/85">
          ورود با کد یکبارمصرف، نقش‌ها و دسترسی‌ها، و پنل مدیریت آماده شده‌اند. بخش
          کسب‌وکارها، استعلام قیمت و نقشه در فازهای بعدی اضافه می‌شود.
        </p>
      </section>

      {user ? (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-500">حساب شما</p>
          <p className="mt-1 text-lg font-bold text-slate-900" dir="ltr">
            {formatPhone(user.phone)}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            {user.is_phone_verified ? "شماره تأیید شده" : "شماره تأیید نشده"}
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            {isAdmin(user) && (
              <Link to="/admin">
                <Button size="sm">ورود به پنل مدیریت</Button>
              </Link>
            )}
            <Button size="sm" variant="outline" onClick={() => void logout()}>
              خروج
            </Button>
          </div>
        </section>
      ) : (
        <section className="mt-6 rounded-2xl border border-slate-200 bg-white p-5">
          <p className="text-sm text-slate-600">برای استفاده از نومکس وارد شوید.</p>
          <Link to="/login" className="mt-4 inline-block">
            <Button>ورود / ثبت‌نام</Button>
          </Link>
        </section>
      )}
    </main>
  );
}
