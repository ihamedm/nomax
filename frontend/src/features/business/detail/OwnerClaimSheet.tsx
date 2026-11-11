import { useEffect, useState, type FormEvent } from "react";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { normalizeDigits } from "@/lib/digits";
import { fa, formatPhone } from "@/lib/format";
import { isValidNationalId } from "@/lib/national-id";
import type { LoginResult } from "@/types";

interface OwnerClaimSheetProps {
  open: boolean;
  businessId: string;
  ownerName?: string | null;
  ownerPhone?: string | null;
  onClose: () => void;
  onClaimed: (result: LoginResult) => void;
}

/**
 * Two-step ownership claim: prove control of the owner phone with an OTP,
 * then set the profile (full name, national ID, password) on that account.
 */
export function OwnerClaimSheet({
  open,
  businessId,
  ownerName,
  ownerPhone,
  onClose,
  onClaimed,
}: OwnerClaimSheetProps) {
  const toast = useToast();
  const [step, setStep] = useState<"otp" | "profile">("otp");
  const [sent, setSent] = useState(false);
  const [code, setCode] = useState("");
  const [fullName, setFullName] = useState("");
  const [nationalId, setNationalId] = useState("");
  const [password, setPassword] = useState("");
  const [retype, setRetype] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setStep("otp");
    setSent(false);
    setCode("");
    // The admin-created owner already has a name; keep it editable.
    setFullName(ownerName?.trim() ?? "");
    setNationalId("");
    setPassword("");
    setRetype("");
    setLoading(false);
    setError(null);
    // Reset only when the sheet opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  async function sendCode() {
    setLoading(true);
    setError(null);
    try {
      const result = await api<{ status: string; dev_otp?: string }>(
        `/businesses/${businessId}/claim/otp`,
        { method: "POST" },
      );
      setSent(true);
      if (result.dev_otp) {
        setCode(result.dev_otp);
        toast(`کد تأیید آزمایشی: ${fa(result.dev_otp)}`);
      } else {
        toast("کد تأیید به شماره مالک پیامک شد.");
      }
    } catch (sendError) {
      setError(errorMessage(sendError));
    } finally {
      setLoading(false);
    }
  }

  async function verifyCode(event: FormEvent) {
    event.preventDefault();
    if (!/^\d{6}$/.test(code)) {
      setError("کد تأیید باید ۶ رقم باشد.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api(`/businesses/${businessId}/claim/otp/verify`, {
        method: "POST",
        body: JSON.stringify({ code }),
      });
      setStep("profile");
      setError(null);
    } catch (verifyError) {
      setError(errorMessage(verifyError));
    } finally {
      setLoading(false);
    }
  }

  async function submitProfile(event: FormEvent) {
    event.preventDefault();
    if (fullName.trim().length < 3) {
      setError("نام و نام خانوادگی را کامل وارد کنید.");
      return;
    }
    if (!isValidNationalId(nationalId)) {
      setError("کد ملی واردشده معتبر نیست.");
      return;
    }
    if (password.length < 8) {
      setError("رمز عبور باید حداقل ۸ کاراکتر باشد.");
      return;
    }
    if (password !== retype) {
      setError("تکرار رمز عبور با رمز عبور یکسان نیست.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const result = await api<LoginResult>(
        `/businesses/${businessId}/claim/profile`,
        {
          method: "POST",
          body: JSON.stringify({
            full_name: fullName.trim(),
            national_id: nationalId,
            password,
          }),
        },
      );
      onClaimed(result);
    } catch (claimError) {
      setError(errorMessage(claimError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title={step === "otp" ? "احراز مالکیت کسب‌وکار" : "تکمیل پروفایل مالک"}
    >
      {step === "otp" ? (
        <form onSubmit={verifyCode} className="space-y-4">
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800">
            <p className="text-sm font-bold">برای تأیید مالکیت، کد یکبارمصرف می‌فرستیم</p>
            <p className="mt-2 text-xs leading-6 text-amber-700">
              کد تأیید به شماره مالک این کسب‌وکار
              {ownerPhone ? (
                <span dir="ltr" className="mx-1 font-bold">
                  {formatPhone(ownerPhone)}
                </span>
              ) : (
                " "
              )}
              پیامک می‌شود. اگر به این شماره دسترسی ندارید، مالکیت قابل ثبت نیست.
            </p>
          </div>

          {sent && (
            <div>
              <label
                htmlFor="claim-otp"
                className="mb-2 block text-sm font-medium text-slate-700"
              >
                کد تأیید ۶ رقمی
              </label>
              <Input
                id="claim-otp"
                inputMode="numeric"
                dir="ltr"
                maxLength={6}
                placeholder="------"
                className="text-center tracking-[0.5em]"
                value={code}
                onChange={(event) =>
                  setCode(normalizeDigits(event.target.value).replace(/\D/g, "").slice(0, 6))
                }
                autoFocus
              />
            </div>
          )}

          {error && (
            <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700">
              {error}
            </p>
          )}

          {sent ? (
            <>
              <Button type="submit" size="lg" className="w-full" loading={loading}>
                تأیید کد
              </Button>
              <button
                type="button"
                disabled={loading}
                onClick={() => void sendCode()}
                className="w-full py-1 text-center text-xs text-brand-600 hover:text-brand-700 disabled:opacity-60"
              >
                ارسال دوباره کد
              </button>
            </>
          ) : (
            <Button
              type="button"
              size="lg"
              className="w-full"
              loading={loading}
              onClick={() => void sendCode()}
            >
              ارسال کد تأیید
            </Button>
          )}
        </form>
      ) : (
        <form onSubmit={submitProfile} className="space-y-4">
          <p className="rounded-xl bg-brand-50 px-3 py-2 text-[11px] leading-5 text-brand-800">
            شماره مالک تأیید شد. حالا نام، کد ملی و رمز عبور حساب مالک را کامل کنید.
            کد ملی با همین شماره در سامانه شاهکار بررسی می‌شود.
          </p>

          <div>
            <label
              htmlFor="claim-full-name"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              نام و نام خانوادگی
            </label>
            <Input
              id="claim-full-name"
              autoComplete="name"
              value={fullName}
              onChange={(event) => setFullName(event.target.value)}
            />
          </div>

          <div>
            <label
              htmlFor="claim-national-id"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              کد ملی
            </label>
            <Input
              id="claim-national-id"
              inputMode="numeric"
              dir="ltr"
              maxLength={10}
              placeholder="۱۰ رقم کد ملی"
              className="text-left"
              value={nationalId}
              onChange={(event) =>
                setNationalId(
                  normalizeDigits(event.target.value).replace(/\D/g, "").slice(0, 10),
                )
              }
            />
          </div>

          <div>
            <label
              htmlFor="claim-password"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              رمز عبور
            </label>
            <Input
              id="claim-password"
              type="password"
              autoComplete="new-password"
              dir="ltr"
              className="text-left"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
            />
          </div>

          <div>
            <label
              htmlFor="claim-retype"
              className="mb-2 block text-sm font-medium text-slate-700"
            >
              تکرار رمز عبور
            </label>
            <Input
              id="claim-retype"
              type="password"
              autoComplete="new-password"
              dir="ltr"
              className="text-left"
              value={retype}
              onChange={(event) => setRetype(event.target.value)}
            />
          </div>

          {error && (
            <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700">
              {error}
            </p>
          )}

          <Button type="submit" size="lg" className="w-full" loading={loading}>
            {loading ? "در حال بررسی با سامانه شاهکار…" : "ثبت مالکیت"}
          </Button>
        </form>
      )}
    </BottomSheet>
  );
}
