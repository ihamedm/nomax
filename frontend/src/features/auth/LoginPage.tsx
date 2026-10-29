import { useRef, useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { splitLoginTarget } from "@/lib/auth-redirect";
import { normalizeDigits } from "@/lib/digits";
import { fa } from "@/lib/format";
import { isLocal } from "@/lib/platform";
import { isAdmin, useAuth } from "@/stores/auth";
import type { LoginResult } from "@/types";

const PHONE_PATTERN = /^(?:\+?98|0)?9\d{9}$/;

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();
  const user = useAuth((state) => state.user);
  const setSession = useAuth((state) => state.setSession);
  const { to: next, state: nextState } = splitLoginTarget(searchParams.get("next"));

  const [step, setStep] = useState<"phone" | "code">("phone");
  const [phone, setPhone] = useState("");
  const [code, setCode] = useState("");
  const [devCode, setDevCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  // After OTP verification the session is set imperatively; skip the
  // already-logged-in <Navigate> render so it cannot race the explicit
  // navigate and re-apply a stale `next` URL (e.g. ?review=1).
  const completedLogin = useRef(false);

  if (user && !completedLogin.current) {
    return <Navigate to={next ?? (isAdmin(user) ? "/admin" : "/me")} state={nextState} replace />;
  }

  async function sendOtp() {
    const normalized = normalizeDigits(phone);
    if (!PHONE_PATTERN.test(normalized)) {
      toast("شماره موبایل معتبر نیست.");
      return;
    }
    setLoading(true);
    try {
      const result = await api<{ status: string; dev_otp?: string }>("/auth/otp/request", {
        method: "POST",
        body: JSON.stringify({ phone: normalized }),
      });
      setPhone(normalized);
      setStep("code");
      if (result.dev_otp) {
        setCode(result.dev_otp);
        setDevCode(result.dev_otp);
        toast(`کد ورود آزمایشی: ${fa(result.dev_otp)}`);
      } else {
        toast("کد ورود پیامک شد.");
      }
    } catch (error) {
      toast(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function verifyOtp(event: FormEvent) {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      toast("کد ورود باید ۶ رقم باشد.");
      return;
    }
    setLoading(true);
    try {
      const result = await api<LoginResult>("/auth/otp/verify", {
        method: "POST",
        body: JSON.stringify({ phone, code }),
      });
      completedLogin.current = true;
      setSession(result.access, result.refresh, result.user);
      navigate(next ?? (isAdmin(result.user) ? "/admin" : "/me"), {
        replace: true,
        state: nextState,
      });
    } catch (error) {
      toast(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="flex min-h-[100dvh] flex-col justify-center bg-gradient-to-b from-brand-700 to-brand-500 px-5 py-10">
      <div className="mx-auto w-full max-w-md">
        <div className="mb-8 text-center text-white">
          <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl bg-white/15 text-2xl font-black">
            N
          </div>
          <h1 className="text-2xl font-black tracking-tight">نومکس</h1>
          <p className="mt-2 text-sm text-white/80">بازار محلی کسب‌وکارها و خدمات بهبهان</p>
        </div>

        <div className="rounded-3xl bg-white p-6 shadow-xl">
          {step === "phone" ? (
            <form
              onSubmit={(event) => {
                event.preventDefault();
                void sendOtp();
              }}
              className="space-y-4"
            >
              <div>
                <label htmlFor="phone" className="mb-2 block text-sm font-medium text-slate-700">
                  شماره موبایل
                </label>
                <Input
                  id="phone"
                  inputMode="tel"
                  autoComplete="tel"
                  dir="ltr"
                  placeholder="0912 345 6789"
                  className="text-left"
                  value={phone}
                  onChange={(event) => setPhone(event.target.value)}
                  autoFocus
                />
              </div>
              <Button type="submit" size="lg" className="w-full" loading={loading}>
                دریافت کد ورود
              </Button>
              <p className="text-center text-xs leading-5 text-slate-400">
                با ورود، قوانین استفاده و حریم خصوصی نومکس را می‌پذیرید.
              </p>
            </form>
          ) : (
            <form onSubmit={verifyOtp} className="space-y-4">
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <label htmlFor="code" className="text-sm font-medium text-slate-700">
                    کد ورود
                  </label>
                  <button
                    type="button"
                    className="text-xs text-brand-600"
                    onClick={() => {
                      setStep("phone");
                      setCode("");
                      setDevCode(null);
                    }}
                  >
                    تغییر شماره
                  </button>
                </div>
                <Input
                  id="code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  dir="ltr"
                  maxLength={6}
                  placeholder="– – – – – –"
                  className="text-center text-xl tracking-[0.5em]"
                  value={code}
                  onChange={(event) => setCode(normalizeDigits(event.target.value).replace(/\D/g, "").slice(0, 6))}
                  autoFocus
                />
                <p className="mt-3 text-center text-xs text-slate-500">
                  کد به شماره {fa(phone)} ارسال شد.
                </p>
                {devCode && isLocal && (
                  <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-center text-xs text-amber-700">
                    محیط توسعه: کد ورود {fa(devCode)} است و به‌صورت خودکار پر شده.
                  </p>
                )}
              </div>
              <Button type="submit" size="lg" className="w-full" loading={loading}>
                ورود به نومکس
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="w-full"
                disabled={loading}
                onClick={() => void sendOtp()}
              >
                ارسال دوباره کد
              </Button>
            </form>
          )}
        </div>

        {next && (
          <p className="mt-4 text-center text-xs leading-5 text-white/75">
            پس از ورود به صفحه‌ای که از آن آمده‌اید برمی‌گردید.
          </p>
        )}
      </div>
    </main>
  );
}
