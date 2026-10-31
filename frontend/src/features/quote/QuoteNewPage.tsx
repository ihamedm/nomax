import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import { useAuth } from "@/stores/auth";
import type { Category, Coordinates, Subcategory } from "@/types";
import { CategoryPickerSheet } from "@/features/business/create/CategoryPickerSheet";
import { MapPickerSheet } from "@/features/business/create/MapPickerSheet";

import { CheckIcon, ChevronLeftIcon, PinIcon, SparkIcon } from "./icons";

const STEPS = ["چه چیزی نیاز دارید؟", "کجا لازم دارید؟", "جزئیات درخواست"] as const;
const MAX_DESCRIPTION = 2000;

interface Draft {
  title: string;
  description: string;
  category: Category | null;
  subcategory: Subcategory | null;
  address: string;
  neighborhood: string;
  geo: Coordinates | null;
  isUrgent: boolean;
}

const EMPTY: Draft = {
  title: "",
  description: "",
  category: null,
  subcategory: null,
  address: "",
  neighborhood: "",
  geo: null,
  isUrgent: false,
};

function categoryPath(category: Category | null, subcategory: Subcategory | null): string {
  if (!category) return "";
  return subcategory ? `${category.name} › ${subcategory.name}` : category.name;
}

function FieldLabel({ children, hint }: { children: React.ReactNode; hint?: string }) {
  return (
    <div className="mb-1.5 flex items-baseline justify-between gap-3">
      <label className="text-xs font-bold text-slate-700">{children}</label>
      {hint && <span className="text-[10px] text-slate-400">{hint}</span>}
    </div>
  );
}

function ErrorText({ children }: { children: React.ReactNode }) {
  return <p className="text-xs leading-5 text-rose-600">{children}</p>;
}

export default function QuoteNewPage() {
  const user = useAuth((state) => state.user);
  const navigate = useNavigate();
  const toast = useToast();
  const queryClient = useQueryClient();

  const [step, setStep] = useState(0);
  const [data, setData] = useState<Draft>(EMPTY);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeQuoteId, setActiveQuoteId] = useState<string | null>(null);

  function patch(partial: Partial<Draft>) {
    setData((current) => ({ ...current, ...partial }));
    setError(null);
    setActiveQuoteId(null);
  }

  function validate(currentStep: number): string | null {
    if (currentStep === 0) {
      if (!data.title.trim()) return "شرح خدمت یا کالای مورد نیاز را وارد کنید.";
      if (data.title.trim().length < 3) return "شرح درخواست باید حداقل ۳ نویسه باشد.";
      if (!data.category) return "دسته‌بندی درخواست را انتخاب کنید.";
    }
    if (currentStep === 1 && data.address.trim().length < 5) {
      return "آدرس دقیق محل دریافت خدمت یا کالا را وارد کنید.";
    }
    if (currentStep === 2 && data.description.length > MAX_DESCRIPTION) {
      return "توضیحات تکمیلی بیش از حد طولانی است.";
    }
    return null;
  }

  function next() {
    const message = validate(step);
    if (message) {
      setError(message);
      return;
    }
    if (step < STEPS.length - 1) {
      setStep((current) => current + 1);
      window.scrollTo({ top: 0, behavior: "smooth" });
      return;
    }
    void submit();
  }

  function back() {
    setError(null);
    setStep((current) => Math.max(0, current - 1));
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  async function submit() {
    if (!data.category) return;
    setSubmitting(true);
    setError(null);
    try {
      await api("/quotes/requests", {
        method: "POST",
        body: JSON.stringify({
          title: data.title.trim(),
          description: data.description.trim() || null,
          category_id: data.category.id,
          subcategory_id: data.subcategory?.id ?? null,
          address: data.address.trim(),
          neighborhood: data.neighborhood.trim() || null,
          geo_lat: data.geo?.lat ?? null,
          geo_lng: data.geo?.lng ?? null,
          is_urgent: data.isUrgent,
        }),
      });
      await queryClient.invalidateQueries({ queryKey: ["quotes"] });
      toast("درخواست شما ثبت شد و برای کسب‌وکارهای مرتبط ارسال می‌شود.");
      navigate("/quote/mine");
    } catch (submitError) {
      if (submitError instanceof ApiError && submitError.message === "active_quote_exists") {
        const details = submitError.details as { quote_id?: string } | undefined;
        setActiveQuoteId(details?.quote_id ?? "");
        setError("شما یک درخواست فعال دارید. تا بسته شدن آن نمی‌توانید درخواست جدید ثبت کنید.");
      } else {
        setError(errorMessage(submitError));
      }
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-3.5rem)] w-full max-w-lg flex-col px-4 pb-0 pt-3">
      <header className="sticky top-14 z-20 -mx-4 mb-4 border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <span className="shrink-0 text-xs font-bold text-slate-500">
            گام {toFa(step + 1)} از {toFa(STEPS.length)}
          </span>
          <h1 className="truncate text-sm font-black text-slate-900">{STEPS[step]}</h1>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-brand-600 transition-all duration-300"
            style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
          />
        </div>
      </header>

      <div className="flex-1 pb-24">
      {step === 0 && (
        <section className="space-y-4">
          <div className="rounded-2xl border border-brand-200 bg-brand-50 p-4">
            <div className="flex items-center gap-2 text-brand-700">
              <SparkIcon className="h-4 w-4" />
              <p className="text-xs font-black">درخواست شما ناشناس است</p>
            </div>
            <p className="mt-2 text-[11px] leading-6 text-slate-600">
              شماره شما فقط پس از انتخاب یکی از پیشنهادها برای همان کسب‌وکار نمایش داده
              می‌شود.
            </p>
            <div className="mt-3 grid grid-cols-3 gap-1.5 text-center text-[10px] text-slate-500">
              <span className="rounded-xl bg-white/70 px-2 py-2">ثبت نیاز</span>
              <span className="rounded-xl bg-white/70 px-2 py-2">دریافت پیشنهاد</span>
              <span className="rounded-xl bg-white/70 px-2 py-2">انتخاب و تماس</span>
            </div>
          </div>

          <div>
            <FieldLabel hint="حداقل ۳ نویسه">چه خدمت یا کالایی نیاز دارید؟</FieldLabel>
            <Input
              value={data.title}
              onChange={(event) => patch({ title: event.target.value })}
              placeholder="مثلاً تعمیر کولر گازی"
              maxLength={160}
            />
          </div>

          <div>
            <FieldLabel>دسته‌بندی</FieldLabel>
            <button
              type="button"
              onClick={() => setCategoryOpen(true)}
              className={cn(
                "flex w-full items-center justify-between gap-3 rounded-xl border-2 border-dashed px-4 py-4 text-right transition-colors",
                data.category
                  ? "border-brand-300 bg-brand-50"
                  : "border-slate-300 bg-white hover:border-brand-300",
              )}
            >
              <span className="min-w-0">
                {data.category ? (
                  <span className="block truncate text-sm font-bold text-brand-700">
                    {data.category.icon} {categoryPath(data.category, data.subcategory)}
                  </span>
                ) : (
                  <span className="block text-sm text-slate-400">
                    انتخاب دسته و زیردسته
                  </span>
                )}
              </span>
              {data.category ? (
                <CheckIcon className="h-4 w-4 shrink-0 text-brand-600" />
              ) : (
                <ChevronLeftIcon className="h-4 w-4 shrink-0 text-slate-400" />
              )}
            </button>
          </div>
        </section>
      )}

      {step === 1 && (
        <section className="space-y-4">
          <div>
            <FieldLabel hint="الزامی">آدرس محل دریافت خدمت / کالا</FieldLabel>
            <textarea
              rows={3}
              value={data.address}
              onChange={(event) => patch({ address: event.target.value })}
              placeholder="مثلاً: بهبهان، خیابان شهید بهشتی، کوچه ۴، پلاک ۱۲"
              maxLength={255}
              className="w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div>
            <FieldLabel hint="اختیاری">محله / محدوده</FieldLabel>
            <Input
              value={data.neighborhood}
              onChange={(event) => patch({ neighborhood: event.target.value })}
              placeholder="مثلاً مرکز شهر"
              maxLength={120}
            />
          </div>

          <div>
            <FieldLabel hint="اختیاری">موقعیت روی نقشه</FieldLabel>
            <button
              type="button"
              onClick={() => setMapOpen(true)}
              className={cn(
                "flex w-full items-center gap-3 rounded-xl border border-dashed px-4 py-3 text-right transition-colors",
                data.geo
                  ? "border-brand-300 bg-brand-50"
                  : "border-slate-300 bg-white hover:border-brand-300",
              )}
            >
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-white text-brand-600 shadow-sm">
                <PinIcon className="h-4 w-4" />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-xs font-bold text-slate-800">
                  {data.geo ? "موقعیت انتخاب شد" : "انتخاب موقعیت روی نقشه"}
                </span>
                <span className="mt-0.5 block truncate text-[10px] text-slate-400" dir="ltr">
                  {data.geo
                    ? `${data.geo.lat.toFixed(5)}, ${data.geo.lng.toFixed(5)}`
                    : "هرچه موقعیت دقیق‌تر باشد، پیشنهادهای نزدیک‌تری می‌گیرید."}
                </span>
              </span>
              <ChevronLeftIcon className="h-4 w-4 shrink-0 text-slate-400" />
            </button>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-center gap-2">
              <span className="flex h-8 w-8 items-center justify-center rounded-xl bg-brand-50 text-brand-600">
                <SparkIcon className="h-4 w-4" />
              </span>
              <div>
                <p className="text-xs font-bold text-slate-900">پیشنهادهای نزدیک</p>
                <p className="mt-0.5 text-[10px] text-slate-400">
                  درخواست برای کسب‌وکارهای هم‌دسته در شعاع ۱۰ کیلومتری ارسال می‌شود.
                </p>
              </div>
            </div>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <p className="text-xs font-black text-slate-900">خلاصه درخواست</p>
            <p className="mt-2 text-sm font-bold text-slate-800">{data.title}</p>
            <p className="mt-1 text-[11px] text-slate-500">
              {data.category?.icon} {categoryPath(data.category, data.subcategory)}
            </p>
            <p className="mt-2 rounded-xl bg-slate-50 px-3 py-2 text-[11px] leading-6 text-slate-500">
              {data.address}
            </p>
          </div>

          <label
            className={cn(
              "flex cursor-pointer items-start gap-3 rounded-2xl border p-4 transition-colors",
              data.isUrgent
                ? "border-amber-300 bg-amber-50"
                : "border-slate-200 bg-white",
            )}
          >
            <input
              type="checkbox"
              className="mt-0.5 h-4 w-4 accent-amber-500"
              checked={data.isUrgent}
              onChange={(event) => patch({ isUrgent: event.target.checked })}
            />
            <span className="min-w-0 flex-1">
              <span className="flex flex-wrap items-center gap-2">
                <span className="text-sm font-bold text-slate-900">درخواست فوری</span>
                <Badge tone="amber">مهلت ۲ ساعت</Badge>
              </span>
              <span className="mt-1 block text-[11px] leading-6 text-slate-500">
                برای کارهای اورژانسی؛ پیشنهادها به کسب‌وکارهای مرتبط ارسال می‌شود و
                پس از ۲ ساعت درخواست منقضی می‌شود.
              </span>
            </span>
          </label>

          <div>
            <FieldLabel hint={`${toFa(data.description.length)} از ${toFa(MAX_DESCRIPTION)}`}>
              توضیحات تکمیلی (اختیاری)
            </FieldLabel>
            <textarea
              rows={4}
              value={data.description}
              onChange={(event) =>
                patch({ description: event.target.value.slice(0, MAX_DESCRIPTION) })
              }
              placeholder="مثلاً مدل دستگاه، حدود قیمت مورد انتظار یا زمان مناسب مراجعه…"
              maxLength={MAX_DESCRIPTION}
              className="w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-3 text-[11px] leading-6 text-slate-500">
            با ثبت درخواست، شماره تماس شما برای کسب‌وکارها نمایش داده نمی‌شود. فقط
            پس از انتخاب یک پیشنهاد، همان کسب‌وکار به شماره شما دسترسی دارد.
          </div>
        </section>
      )}
      </div>

      <div className="sticky bottom-0 z-30 -mx-4 mt-auto border-t border-slate-200 bg-white px-4 pb-[calc(env(safe-area-inset-bottom,0px)+0.75rem)] pt-4">
        {error && (
          <div className="mb-2 space-y-1.5">
            <ErrorText>{error}</ErrorText>
            {activeQuoteId !== null && (
              <Link
                to={activeQuoteId ? `/quote/mine/${activeQuoteId}` : "/quote/mine"}
                className="inline-block text-xs font-bold text-brand-600"
              >
                مشاهده درخواست فعال ←
              </Link>
            )}
          </div>
        )}
        <div className="flex gap-2">
          {step > 0 && (
            <Button type="button" variant="outline" className="flex-1" onClick={back}>
              مرحله قبل
            </Button>
          )}
          <Button type="button" className="flex-1" loading={submitting} onClick={next}>
            {step === STEPS.length - 1 ? "ثبت درخواست" : "مرحله بعد"}
          </Button>
        </div>
        {user && step === 0 && (
          <p className="mt-3 text-center text-[10px] text-slate-400">
            ثبت درخواست با حساب {user.full_name || "شماره شما"}
          </p>
        )}
      </div>

      <CategoryPickerSheet
        open={categoryOpen}
        onClose={() => setCategoryOpen(false)}
        selected={data.category}
        selectedSubcategory={data.subcategory}
        onSelect={(category, subcategory) => patch({ category, subcategory })}
      />
      <MapPickerSheet
        open={mapOpen}
        title="موقعیت درخواست"
        locationLabel="موقعیت درخواست"
        address={data.address}
        value={data.geo}
        onClose={() => setMapOpen(false)}
        onConfirm={(address, geo) => {
          patch({ address: address || data.address, geo });
          setMapOpen(false);
        }}
      />
    </div>
  );
}
