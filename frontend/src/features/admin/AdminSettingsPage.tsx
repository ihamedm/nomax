import { useEffect, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useSearchParams } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage, type ApiError } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useApi } from "@/lib/query";
import { QuoteDispatchHelp } from "./QuoteDispatchHelp";

interface QuoteDispatchSettings {
  enabled: boolean;
  initial_batch_size: number;
  retry_batch_size: number;
  min_target_deliveries: number;
  max_rounds: number;
  response_window_minutes: number;
  urgent_response_window_minutes: number;
  advance_on_seen: boolean;
  dispatch_radius_km: number;
  expand_radius_km: number;
  subcategory_fallback: boolean;
  fallback_outside_radius: boolean;
  day_start_hour: number;
  day_end_hour: number;
  allow_urgent_at_night: boolean;
  no_candidate_retry_minutes: number;
}

interface SettingsResponse {
  search_trends: string[];
  quote_dispatch: QuoteDispatchSettings;
  quote_dispatch_defaults: QuoteDispatchSettings;
}

type DispatchKey = keyof QuoteDispatchSettings;

const TABS = [
  { value: "general", label: "محتوا و جستجو" },
  { value: "dispatch", label: "ارسال استعلام" },
] as const;

function Toggle({
  checked,
  onChange,
  label,
  hint,
}: {
  checked: boolean;
  onChange: (value: boolean) => void;
  label: string;
  hint: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3 rounded-xl border border-slate-200 bg-white px-3 py-2.5">
      <span className="min-w-0">
        <span className="block text-[11px] font-bold text-slate-800">{label}</span>
        <span className="mt-0.5 block text-[10px] leading-5 text-slate-400">{hint}</span>
      </span>
      <button
        type="button"
        role="switch"
        aria-checked={checked}
        aria-label={label}
        onClick={() => onChange(!checked)}
        className={cn(
          "relative mt-0.5 h-5 w-9 shrink-0 rounded-full transition-colors",
          checked ? "bg-brand-600" : "bg-slate-300",
        )}
      >
        <span
          className={cn(
            "absolute top-0.5 h-4 w-4 rounded-full bg-white shadow-sm transition-all",
            checked ? "right-0.5" : "right-[18px]",
          )}
        />
      </button>
    </div>
  );
}

function NumberField({
  label,
  hint,
  value,
  onChange,
  suffix,
  min,
  max,
  step = 1,
}: {
  label: string;
  hint: string;
  value: number;
  onChange: (value: number) => void;
  suffix: string;
  min: number;
  max: number;
  step?: number;
}) {
  return (
    <label className="block rounded-xl border border-slate-200 bg-white px-3 py-2.5">
      <span className="block text-[11px] font-bold text-slate-800">{label}</span>
      <span className="mt-0.5 block min-h-5 text-[10px] leading-5 text-slate-400">{hint}</span>
      <span className="mt-1.5 flex items-center gap-1.5">
        <input
          type="number"
          dir="ltr"
          value={Number.isFinite(value) ? value : ""}
          min={min}
          max={max}
          step={step}
          onChange={(event) => {
            const next = Number(event.target.value);
            if (event.target.value === "") onChange(min);
            else if (Number.isFinite(next)) onChange(next);
          }}
          className="h-9 w-full rounded-lg border border-slate-200 bg-slate-50 px-2 text-left text-xs font-bold text-slate-800 focus:border-brand-500 focus:bg-white focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        />
        <span className="shrink-0 text-[10px] text-slate-400">{suffix}</span>
      </span>
    </label>
  );
}

export default function AdminSettingsPage() {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") === "dispatch" ? "dispatch" : "general";
  const { data, isLoading, error } = useApi<SettingsResponse>(
    ["admin", "settings"],
    "/admin/settings",
  );
  const [terms, setTerms] = useState("");
  const [dispatch, setDispatch] = useState<QuoteDispatchSettings | null>(null);
  const [helpOpen, setHelpOpen] = useState(false);

  useEffect(() => {
    if (data) setTerms(data.search_trends.join("\n"));
  }, [data]);

  useEffect(() => {
    if (data?.quote_dispatch) setDispatch(data.quote_dispatch);
  }, [data]);

  const save = useMutation({
    mutationFn: (value: string[]) =>
      api("/admin/settings/search_trends", {
        method: "PUT",
        body: JSON.stringify({ value }),
      }),
    onSuccess: () => {
      toast("جستجوهای پرطرفدار ذخیره شد.");
      void queryClient.invalidateQueries({ queryKey: ["admin", "settings"] });
      void queryClient.invalidateQueries({ queryKey: ["search", "trending"] });
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  const saveDispatch = useMutation({
    mutationFn: (value: QuoteDispatchSettings) =>
      api("/admin/settings/quote_dispatch", {
        method: "PUT",
        body: JSON.stringify({ value }),
      }),
    onSuccess: () => {
      toast("تنظیمات ارسال استعلام ذخیره شد. از این پس دورهای بعدی با همین مقادیر اجرا می‌شوند.");
      void queryClient.invalidateQueries({ queryKey: ["admin", "settings"] });
    },
    onError: (err: ApiError) => toast(errorMessage(err)),
  });

  function update<K extends DispatchKey>(key: K, value: QuoteDispatchSettings[K]) {
    setDispatch((current) => (current ? { ...current, [key]: value } : current));
  }

  function submitDispatch() {
    if (!dispatch) return;
    if (dispatch.day_start_hour >= dispatch.day_end_hour) {
      toast("ساعت شروع باید قبل از ساعت پایان باشد.");
      return;
    }
    if (dispatch.expand_radius_km < dispatch.dispatch_radius_km) {
      toast("شعاع توسعه نباید کمتر از شعاع اصلی باشد.");
      return;
    }
    saveDispatch.mutate(dispatch);
  }

  return (
    <div className="max-w-5xl space-y-4">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">تنظیمات</h1>
          <p className="mt-1 text-xs text-slate-500">
            محتوای صفحه اصلی و استراتژی ارسال استعلام به کسب‌وکارها
          </p>
        </div>
        <div className="flex flex-wrap items-center justify-end gap-2">
          <button
            type="button"
            onClick={() => setHelpOpen(true)}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl border border-brand-200 bg-white px-3 text-[11px] font-bold text-brand-700 transition-colors hover:bg-brand-50"
          >
            <span className="flex h-4 w-4 items-center justify-center rounded-full bg-brand-100 text-[10px] font-black">
              ؟
            </span>
            راهنمای ارسال استعلام
          </button>
          <div className="flex rounded-xl border border-slate-200 bg-white p-1">
            {TABS.map((item) => (
              <button
                key={item.value}
                type="button"
                onClick={() =>
                  setParams(item.value === "general" ? {} : { tab: item.value })
                }
                className={cn(
                  "rounded-lg px-3 py-1.5 text-[11px] font-bold transition-colors",
                  tab === item.value
                    ? "bg-brand-600 text-white"
                    : "text-slate-500 hover:bg-slate-50",
                )}
              >
                {item.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}
      {isLoading && <p className="py-8 text-center text-xs text-slate-400">در حال بارگذاری…</p>}

      {tab === "general" && (
        <div className="rounded-2xl border border-slate-200 bg-white p-5">
          <div className="flex items-start justify-between gap-4">
            <div>
              <p className="text-sm font-bold text-slate-900">جستجوهای پرطرفدار</p>
              <p className="mt-1 text-xs leading-6 text-slate-500">
                هر عبارت در یک خط. این موارد در صفحه جستجو و زیر فرم جستجوی صفحه
                اصلی نمایش داده می‌شوند.
              </p>
            </div>
            <span className="rounded-full bg-slate-100 px-2.5 py-1 text-[10px] text-slate-500">
              {terms.split("\n").filter((term) => term.trim()).length} عبارت
            </span>
          </div>
          <textarea
            value={terms}
            onChange={(event) => setTerms(event.target.value)}
            disabled={isLoading}
            rows={9}
            className="mt-3 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            placeholder={"تعمیر کولر\nلوله‌کشی\nبرق‌کاری"}
          />
          <div className="mt-3">
            <Button
              loading={save.isPending}
              onClick={() =>
                save.mutate(
                  terms
                    .split("\n")
                    .map((term) => term.trim())
                    .filter(Boolean),
                )
              }
            >
              ذخیره تنظیمات
            </Button>
          </div>
        </div>
      )}

      {tab === "dispatch" && dispatch && (
        <div className="space-y-3">
          <div className="rounded-2xl border border-brand-100 bg-brand-50/60 px-4 py-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <p className="text-sm font-black text-brand-800">استراتژی ارسال چندموجی</p>
                <p className="mt-1 text-[11px] leading-6 text-brand-700/80">
                  درخواست ابتدا به یک گروه کوچک می‌رود؛ اگر در بازه تعیین‌شده
                  مشاهده یا پیشنهادی ثبت نشود، موج بعدی به صاحبان تازه ارسال
                  می‌شود. زمان‌ها بر اساس ساعت تهران است.
                </p>
              </div>
              <span className="rounded-full bg-white px-2.5 py-1 text-[10px] font-bold text-brand-700">
                {dispatch.enabled ? "فعال" : "غیرفعال"}
              </span>
            </div>
          </div>

          <div className="grid gap-2 md:grid-cols-2">
            <Toggle
              checked={dispatch.enabled}
              onChange={(value) => update("enabled", value)}
              label="ارسال خودکار فعال باشد"
              hint="با خاموش کردن، درخواست‌ها فقط به‌صورت دستی توسط مدیر ارسال می‌شوند."
            />
            <Toggle
              checked={dispatch.advance_on_seen}
              onChange={(value) => update("advance_on_seen", value)}
              label="موج بعد پس از مشاهده بدون پیشنهاد"
              hint="اگر کسب‌وکار درخواست را ببیند اما پیشنهاد ندهد، پس از پایان بازه به صاحبان تازه ارسال شود."
            />
          </div>

          <div className="pt-1">
            <p className="mb-2 text-xs font-black text-slate-800">اندازه موج‌ها و زمان پاسخ</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <NumberField label="تعداد صاحبان در موج اول" hint="درخواست تازه به چند کسب‌وکار برود." value={dispatch.initial_batch_size} onChange={(value) => update("initial_batch_size", value)} suffix="کسب‌وکار" min={1} max={20} />
              <NumberField label="تعداد صاحبان در موج‌های بعد" hint="هر دور تمدید چند صاحب تازه اضافه شود." value={dispatch.retry_batch_size} onChange={(value) => update("retry_batch_size", value)} suffix="کسب‌وکار" min={1} max={20} />
              <NumberField label="حداقل کسب‌وکار هدف" hint="اگر کسب‌وکار کافی نبود، از شعاع/دسته گسترده‌تر پر شود." value={dispatch.min_target_deliveries} onChange={(value) => update("min_target_deliveries", value)} suffix="کسب‌وکار" min={1} max={20} />
              <NumberField label="حداکثر تعداد موج" hint="پس از این تعداد، ارسال خودکار متوقف می‌شود." value={dispatch.max_rounds} onChange={(value) => update("max_rounds", value)} suffix="موج" min={1} max={10} />
              <NumberField label="بازه پاسخ عادی" hint="مدت انتظار برای مشاهده/پیشنهاد در درخواست عادی." value={dispatch.response_window_minutes} onChange={(value) => update("response_window_minutes", value)} suffix="دقیقه" min={5} max={1440} />
              <NumberField label="بازه پاسخ فوری" hint="مدت انتظار کوتاه‌تر برای درخواست فوری." value={dispatch.urgent_response_window_minutes} onChange={(value) => update("urgent_response_window_minutes", value)} suffix="دقیقه" min={1} max={120} />
              <NumberField label="بازه جستجوی مجدد" hint="اگر هنوز کسب‌وکار مناسبی پیدا نشد، هر چند دقیقه دوباره بررسی شود." value={dispatch.no_candidate_retry_minutes} onChange={(value) => update("no_candidate_retry_minutes", value)} suffix="دقیقه" min={5} max={1440} />
            </div>
          </div>

          <div className="pt-1">
            <p className="mb-2 text-xs font-black text-slate-800">شعاع و تطبیق دسته‌بندی</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
              <NumberField label="شعاع اصلی" hint="اولویت اول ارسال در این محدوده است." value={dispatch.dispatch_radius_km} onChange={(value) => update("dispatch_radius_km", value)} suffix="کیلومتر" min={0.5} max={100} step={0.5} />
              <NumberField label="شعاع توسعه" hint="اگر در شعاع اصلی کافی نبود، تا این محدوده گسترش یابد." value={dispatch.expand_radius_km} onChange={(value) => update("expand_radius_km", value)} suffix="کیلومتر" min={1} max={200} step={0.5} />
              <div className="rounded-xl border border-slate-200 bg-white px-3 py-2.5">
                <p className="text-[11px] font-bold text-slate-800">قواعد پوشش</p>
                <p className="mt-0.5 text-[10px] leading-5 text-slate-400">
                  دو کلید زیر تضمین می‌کنند درخواست بدون صاحب نماند.
                </p>
                <div className="mt-2 space-y-1.5">
                  <label className="flex items-center gap-2 text-[10px] text-slate-600">
                    <input type="checkbox" checked={dispatch.subcategory_fallback} onChange={(event) => update("subcategory_fallback", event.target.checked)} className="h-3.5 w-3.5 accent-brand-600" />
                    در نبود زیردسته دقیق، کل دسته بررسی شود
                  </label>
                  <label className="flex items-center gap-2 text-[10px] text-slate-600">
                    <input type="checkbox" checked={dispatch.fallback_outside_radius} onChange={(event) => update("fallback_outside_radius", event.target.checked)} className="h-3.5 w-3.5 accent-brand-600" />
                    در نبود گزینه، خارج از شعاع هم ارسال شود
                  </label>
                </div>
              </div>
            </div>
          </div>

          <div className="pt-1">
            <p className="mb-2 text-xs font-black text-slate-800">پنجره ارسال و درخواست فوری</p>
            <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
              <NumberField label="ساعت شروع ارسال" hint="به وقت تهران." value={dispatch.day_start_hour} onChange={(value) => update("day_start_hour", value)} suffix="ساعت" min={0} max={23} />
              <NumberField label="ساعت پایان ارسال" hint="پس از این ساعت، ارسال عادی به صبح موکول می‌شود." value={dispatch.day_end_hour} onChange={(value) => update("day_end_hour", value)} suffix="ساعت" min={1} max={24} />
              <div className="sm:col-span-2">
                <Toggle
                  checked={dispatch.allow_urgent_at_night}
                  onChange={(value) => update("allow_urgent_at_night", value)}
                  label="ارسال درخواست فوری در شب"
                  hint="ابتدا کسب‌وکارهای شبانه‌روزی؛ در نبود آن‌ها سایر صاحبان همان دسته."
                />
              </div>
            </div>
          </div>

          <div className="sticky bottom-3 flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-slate-200 bg-white/95 px-3 py-2.5 shadow-sm backdrop-blur">
            <div className="flex items-center gap-2">
              <Button loading={saveDispatch.isPending} onClick={submitDispatch}>
                ذخیره استراتژی ارسال
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={() => data && setDispatch(data.quote_dispatch_defaults)}
              >
                بازگشت به پیش‌فرض
              </Button>
            </div>
            <p className="text-[10px] text-slate-400">
              تغییرات از موج بعدی اعمال می‌شود؛ درخواست‌های در حال اجرا متوقف نمی‌شوند.
            </p>
          </div>
        </div>
      )}

      <QuoteDispatchHelp open={helpOpen} onClose={() => setHelpOpen(false)} />
    </div>
  );
}
