import { useRef, useState, type FormEvent } from "react";
import { Navigate, useNavigate, useSearchParams } from "react-router-dom";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, ApiError, errorMessage } from "@/lib/api";
import { splitLoginTarget } from "@/lib/auth-redirect";
import { normalizeDigits } from "@/lib/digits";
import { fa } from "@/lib/format";
import { isLocal } from "@/lib/platform";
import { isAdmin, useAuth } from "@/stores/auth";
import type { LoginResult } from "@/types";

const PHONE_PATTERN = /^(?:\+?98|0)?9\d{9}$/;
const PASSWORD_MIN = 8;

type Step = "phone" | "password" | "register" | "forgot" | "reset";

interface SheetError {
  title: string;
  message: string;
  checks: string[];
}

function validNationalId(nid: string): boolean {
  if (!/^\d{10}$/.test(nid)) return false;
  const digits = nid.split("").map(Number);
  const sum = digits.slice(0, 9).reduce((acc, d, i) => acc + d * (10 - i), 0);
  const remainder = sum % 11;
  return digits[9] === (remainder < 2 ? remainder : 11 - remainder);
}

export function LoginPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const toast = useToast();
  const user = useAuth((state) => state.user);
  const setSession = useAuth((state) => state.setSession);
  const { to: next, state: nextState } = splitLoginTarget(searchParams.get("next"));

  const [step, setStep] = useState<Step>("phone");
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [retypePassword, setRetypePassword] = useState("");
  const [resetCode, setResetCode] = useState("");
  const [devResetCode, setDevResetCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [sheetError, setSheetError] = useState<SheetError | null>(null);
  // After OTP verification the session is set imperatively; skip the
  // already-logged-in <Navigate> render so it cannot race the explicit
  // navigate and re-apply a stale `next` URL (e.g. ?review=1).
  const completedLogin = useRef(false);

  if (user && !completedLogin.current) {
    return <Navigate to={next ?? (isAdmin(user) ? "/admin" : "/me")} state={nextState} replace />;
  }

  function resetFieldState() {
    setPassword("");
    setNewPassword("");
    setRetypePassword("");
    setResetCode("");
    setDevResetCode(null);
  }

  function complete(result: LoginResult) {
    completedLogin.current = true;
    setSession(result.access, result.refresh, result.user);
    navigate(next ?? (isAdmin(result.user) ? "/admin" : "/me"), {
      replace: true,
      state: nextState,
    });
  }

  async function checkPhone(event: FormEvent) {
    event.preventDefault();
    const normalized = normalizeDigits(phone);
    if (!PHONE_PATTERN.test(normalized)) {
      toast("شماره موبایل معتبر نیست.");
      return;
    }
    setPhone(normalized);
    setLoading(true);
    try {
      const result = await api<{ registered: boolean }>("/auth/check", {
        method: "POST",
        body: JSON.stringify({ phone: normalized }),
      });
      resetFieldState();
      setStep(result.registered ? "password" : "register");
    } catch (error) {
      toast(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function login(event: FormEvent) {
    event.preventDefault();
    if (!password) {
      toast("رمز عبور را وارد کنید.");
      return;
    }
    setLoading(true);
    try {
      const result = await api<LoginResult>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ phone, password }),
      });
      complete(result);
    } catch (error) {
      setPassword("");
      toast(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  function registerError(error: unknown): SheetError {
    const code = error instanceof ApiError ? error.code : "http_error";
    const details =
      error instanceof ApiError
        ? (error.details as
            | { provider_message?: string; provider_code?: number; retry_after_seconds?: number }
            | undefined)
        : undefined;
    const providerMessage = details?.provider_message?.trim();
    const providerCode =
      typeof details?.provider_code === "number" ? details.provider_code : undefined;
    if (code === "shahkar_mismatch") {
      return {
        title: "شماره موبایل با کد ملی مطابقت ندارد",
        message:
          providerMessage ||
          "بر اساس سامانه شاهکار، این شماره سیم‌کارت به کد ملی واردشده تعلق ندارد.",
        checks: [
          "کد ملی را با کارت ملی خود مقایسه کنید.",
          "اگر سیم‌کارت به نام شماست، با اپراتور تماس بگیرید تا اطلاعات به‌روز شود.",
          "اگر شماره متعلق به کسی دیگر است، با شمارهٔ ثبت‌شده به نام خود ثبت‌نام کنید.",
          ...(providerCode ? [`کد خطای شاهکار: ${fa(providerCode)}`] : []),
        ],
      };
    }
    if (code === "shahkar_invalid_input" || code === "invalid_national_id") {
      return {
        title: "اطلاعات کد ملی یا موبایل معتبر نیست",
        message:
          providerMessage ||
          "کد ملی یا شماره موبایل در سامانه شاهکار معتبر تشخیص داده نشد.",
        checks: [
          "صحت ۱۰ رقم کد ملی را بررسی کنید.",
          "شماره موبایل را دوباره بررسی کنید.",
          ...(providerCode ? [`کد خطای شاهکار: ${fa(providerCode)}`] : []),
        ],
      };
    }
    if (code === "conflict" || code === "phone_already_registered") {
      return {
        title: "این اطلاعات قبلاً ثبت شده است",
        message: "این شماره موبایل یا کد ملی قبلاً در نومکس ثبت شده است.",
        checks: ["از دکمه بازگشت استفاده کنید و وارد شوید.", "اگر رمز خود را فراموش کرده‌اید، گزینه «فراموشی رمز عبور» را بزنید."],
      };
    }
    if (code === "rate_limited") {
      const wait = Math.max(1, Math.ceil((details?.retry_after_seconds ?? 0) / 60));
      return {
        title: "تعداد تلاش‌ها زیاد است",
        message: `برای جلوگیری از سوءاستفاده، تعداد تلاش‌های ثبت‌نام محدود است. حدود ${fa(wait)} دقیقه دیگر دوباره تلاش کنید.`,
        checks: ["تا پایان این بازه، دوباره دکمه ثبت‌نام را نزنید."],
      };
    }
    if (code === "shahkar_unavailable") {
      return {
        title: "خطا در سامانه شاهکار",
        message:
          providerMessage ||
          errorMessage(error) ||
          "بررسی شاهکار در حال حاضر ممکن نیست. کمی بعد تلاش کنید.",
        checks: [
          "چند دقیقه صبر کنید و دوباره تلاش کنید.",
          ...(providerCode ? [`کد خطای شاهکار: ${fa(providerCode)}`] : []),
        ],
      };
    }
    return {
      title: "ثبت‌نام انجام نشد",
      message: errorMessage(error),
      checks: ["اطلاعات فرم را بررسی کنید و دوباره تلاش کنید."],
    };
  }

  async function register(event: FormEvent) {
    event.preventDefault();
    if (fullName.trim().length < 3) {
      toast("نام و نام خانوادگی را کامل وارد کنید.");
      return;
    }
    if (!validNationalId(nationalId)) {
      toast("کد ملی واردشده معتبر نیست.");
      return;
    }
    if (newPassword.length < PASSWORD_MIN) {
      toast("رمز عبور باید حداقل ۸ کاراکتر باشد.");
      return;
    }
    if (newPassword !== retypePassword) {
      toast("تکرار رمز عبور با رمز عبور یکسان نیست.");
      return;
    }
    // While loading the register button shows the Shahkar progress text.
    setLoading(true);
    try {
      const result = await api<LoginResult>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          phone,
          full_name: fullName.trim(),
          national_id: nationalId,
          password: newPassword,
        }),
      });
      complete(result);
    } catch (error) {
      setLoading(false);
      setSheetError(registerError(error));
      return;
    }
    setLoading(false);
  }

  async function sendResetCode() {
    setLoading(true);
    try {
      const result = await api<{ status: string; dev_otp?: string }>("/auth/forgot-password", {
        method: "POST",
        body: JSON.stringify({ phone }),
      });
      resetFieldState();
      setStep("reset");
      if (result.dev_otp) {
        setResetCode(result.dev_otp);
        setDevResetCode(result.dev_otp);
        toast(`کد بازیابی آزمایشی: ${fa(result.dev_otp)}`);
      } else {
        toast("کد تأیید پیامک شد.");
      }
    } catch (error) {
      toast(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }

  async function resetPassword(event: FormEvent) {
    event.preventDefault();
    if (!/^\d{6}$/.test(resetCode)) {
      toast("کد تأیید باید ۶ رقم باشد.");
      return;
    }
    if (newPassword.length < PASSWORD_MIN) {
      toast("رمز عبور جدید باید حداقل ۸ کاراکتر باشد.");
      return;
    }
    if (newPassword !== retypePassword) {
      toast("تکرار رمز عبور با رمز عبور یکسان نیست.");
      return;
    }
    setLoading(true);
    try {
      const result = await api<LoginResult>("/auth/reset-password", {
        method: "POST",
        body: JSON.stringify({ phone, code: resetCode, password: newPassword }),
      });
      complete(result);
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
          {step === "phone" && (
            <form onSubmit={checkPhone} className="space-y-4">
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
                ادامه
              </Button>
              <p className="text-center text-xs leading-5 text-slate-400">
                با ادامه، قوانین استفاده و حریم خصوصی نومکس را می‌پذیرید.
              </p>
            </form>
          )}

          {step === "password" && (
            <form onSubmit={login} className="space-y-4">
              <p className="text-sm text-slate-500">
                ورود با شماره {fa(phone)}
              </p>
              <div>
                <label htmlFor="password" className="mb-2 block text-sm font-medium text-slate-700">
                  رمز عبور
                </label>
                <Input
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  dir="ltr"
                  className="text-left"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  autoFocus
                />
              </div>
              <Button type="submit" size="lg" className="w-full" loading={loading}>
                ورود
              </Button>
              <button
                type="button"
                className="w-full text-center text-sm text-brand-600"
                onClick={() => {
                  resetFieldState();
                  setStep("forgot");
                }}
              >
                رمز عبور را فراموش کرده‌اید؟
              </button>
              <button
                type="button"
                className="w-full text-center text-xs text-slate-400"
                onClick={() => {
                  resetFieldState();
                  setStep("phone");
                }}
              >
                تغییر شماره
              </button>
            </form>
          )}

          {step === "register" && (
            <form onSubmit={register} className="space-y-4">
              <p className="text-sm text-slate-500">
                حسابی برای {fa(phone)} پیدا نشد؛ ثبت‌نام کنید.
              </p>
              <div>
                <label htmlFor="full-name" className="mb-2 block text-sm font-medium text-slate-700">
                  نام و نام خانوادگی
                </label>
                <Input
                  id="full-name"
                  autoComplete="name"
                  value={fullName}
                  onChange={(event) => setFullName(event.target.value)}
                  autoFocus
                />
              </div>
              <div>
                <label htmlFor="national-id" className="mb-2 block text-sm font-medium text-slate-700">
                  کد ملی
                </label>
                <Input
                  id="national-id"
                  inputMode="numeric"
                  dir="ltr"
                  maxLength={10}
                  placeholder="۱۰ رقم کد ملی"
                  className="text-left"
                  value={nationalId}
                  onChange={(event) => setNationalId(normalizeDigits(event.target.value).replace(/\D/g, "").slice(0, 10))}
                />
              </div>
              <div>
                <label htmlFor="new-password" className="mb-2 block text-sm font-medium text-slate-700">
                  رمز عبور
                </label>
                <Input
                  id="new-password"
                  type="password"
                  autoComplete="new-password"
                  dir="ltr"
                  className="text-left"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
              </div>
              <div>
                <label htmlFor="retype-password" className="mb-2 block text-sm font-medium text-slate-700">
                  تکرار رمز عبور
                </label>
                <Input
                  id="retype-password"
                  type="password"
                  autoComplete="new-password"
                  dir="ltr"
                  className="text-left"
                  value={retypePassword}
                  onChange={(event) => setRetypePassword(event.target.value)}
                />
              </div>
              <Button type="submit" size="lg" className="w-full" loading={loading}>
                {loading ? "در حال بررسی با سامانه شاهکار…" : "ثبت‌نام"}
              </Button>
              <button
                type="button"
                className="w-full text-center text-xs text-slate-400"
                disabled={loading}
                onClick={() => {
                  resetFieldState();
                  setStep("phone");
                }}
              >
                تغییر شماره
              </button>
            </form>
          )}

          {step === "forgot" && (
            <div className="space-y-4">
              <p className="text-sm leading-6 text-slate-600">
                کد تأیید برای بازیابی رمز عبور به شماره {fa(phone)} پیامک می‌شود.
              </p>
              <Button
                type="button"
                size="lg"
                className="w-full"
                loading={loading}
                onClick={() => void sendResetCode()}
              >
                ارسال کد تأیید
              </Button>
              <button
                type="button"
                className="w-full text-center text-xs text-slate-400"
                disabled={loading}
                onClick={() => setStep("password")}
              >
                بازگشت به ورود
              </button>
            </div>
          )}

          {step === "reset" && (
            <form onSubmit={resetPassword} className="space-y-4">
              <div>
                <label htmlFor="reset-code" className="text-sm font-medium text-slate-700">
                  کد تأیید
                </label>
                <Input
                  id="reset-code"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  dir="ltr"
                  maxLength={6}
                  placeholder="– – – – – –"
                  className="mt-2 text-center text-xl tracking-[0.5em]"
                  value={resetCode}
                  onChange={(event) => setResetCode(normalizeDigits(event.target.value).replace(/\D/g, "").slice(0, 6))}
                  autoFocus
                />
                <p className="mt-3 text-center text-xs text-slate-500">
                  کد به شماره {fa(phone)} ارسال شد.
                </p>
                {devResetCode && isLocal && (
                  <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-center text-xs text-amber-700">
                    محیط توسعه: کد تأیید {fa(devResetCode)} است و به‌صورت خودکار پر شده.
                  </p>
                )}
              </div>
              <div>
                <label htmlFor="reset-password" className="mb-2 block text-sm font-medium text-slate-700">
                  رمز عبور جدید
                </label>
                <Input
                  id="reset-password"
                  type="password"
                  autoComplete="new-password"
                  dir="ltr"
                  className="text-left"
                  value={newPassword}
                  onChange={(event) => setNewPassword(event.target.value)}
                />
              </div>
              <div>
                <label htmlFor="reset-retype" className="mb-2 block text-sm font-medium text-slate-700">
                  تکرار رمز عبور جدید
                </label>
                <Input
                  id="reset-retype"
                  type="password"
                  autoComplete="new-password"
                  dir="ltr"
                  className="text-left"
                  value={retypePassword}
                  onChange={(event) => setRetypePassword(event.target.value)}
                />
              </div>
              <Button type="submit" size="lg" className="w-full" loading={loading}>
                ثبت رمز جدید
              </Button>
              <Button
                type="button"
                variant="ghost"
                size="sm"
                className="w-full"
                disabled={loading}
                onClick={() => void sendResetCode()}
              >
                ارسال دوباره کد
              </Button>
            </form>
          )}
        </div>

      </div>

      <BottomSheet
        open={sheetError !== null}
        title={sheetError?.title}
        onClose={() => setSheetError(null)}
        className="pb-2"
      >
        <div className="space-y-4 pb-4">
          <ErrorSheetBody error={sheetError} />
          <Button
            type="button"
            size="lg"
            className="w-full"
            onClick={() => setSheetError(null)}
          >
            اصلاح اطلاعات و تلاش مجدد
          </Button>
        </div>
      </BottomSheet>
    </main>
  );
}

function ErrorSheetBody({ error }: { error: SheetError | null }) {
  if (!error) return null;
  return (
    <div className="space-y-2">
      <p className="text-sm leading-6 text-slate-600">{error.message}</p>
      <ul className="space-y-1 rounded-xl bg-slate-50 px-4 py-3 text-sm text-slate-600">
        {error.checks.map((check) => (
          <li key={check} className="list-disc marker:text-slate-300">
            {check}
          </li>
        ))}
      </ul>
    </div>
  );
}
