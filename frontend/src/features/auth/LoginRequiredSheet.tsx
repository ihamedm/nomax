import { Link } from "react-router-dom";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { loginPath } from "@/lib/auth-redirect";

interface LoginRequiredSheetProps {
  open: boolean;
  title: string;
  description: string;
  next: string;
  onClose: () => void;
}

/**
 * Shared inline login gate. It explains why the action needs an account and
 * sends the user to `/login?next=…`; after OTP verification the login page
 * returns them to the same business page.
 */
export function LoginRequiredSheet({
  open,
  title,
  description,
  next,
  onClose,
}: LoginRequiredSheetProps) {
  return (
    <BottomSheet open={open} onClose={onClose} title={title}>
      <div className="space-y-4">
        <div className="rounded-2xl border border-brand-200 bg-brand-50 p-4 text-center">
          <span
            aria-hidden
            className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-white text-2xl shadow-sm"
          >
            🔐
          </span>
          <p className="mt-3 text-sm font-bold text-slate-900">برای ادامه وارد شوید</p>
          <p className="mt-2 text-xs leading-6 text-slate-600">{description}</p>
        </div>

        <p className="rounded-xl bg-slate-50 px-3 py-2 text-center text-[11px] leading-5 text-slate-500">
          با ورود یا ثبت‌نام، به همین صفحه برمی‌گردید و می‌توانید کار خود را ادامه دهید.
        </p>

        <Link
          to={loginPath(next)}
          onClick={onClose}
          className="inline-flex h-11 w-full items-center justify-center rounded-xl bg-brand-600 px-4 text-sm font-medium text-white transition-colors hover:bg-brand-700"
        >
          ورود / ثبت‌نام
        </Link>

        <button
          type="button"
          onClick={onClose}
          className="w-full py-1 text-center text-xs text-slate-500 hover:text-slate-800"
        >
          فعلاً نه، ادامه بدون ورود
        </button>
      </div>
    </BottomSheet>
  );
}
