import { useEffect, useRef, useState } from "react";
import { Link, Navigate, useLocation, useNavigate } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { loginPath, returnPath } from "@/lib/auth-redirect";
import { cn } from "@/lib/cn";
import { normalizeDigits, toFa } from "@/lib/digits";
import { formatPhone } from "@/lib/format";
import {
  MAX_IMAGE_INPUT_BYTES,
  MAX_IMAGE_UPLOAD_BYTES,
  compressImageForUpload,
} from "@/lib/image";
import { useApi } from "@/lib/query";
import { useAuth } from "@/stores/auth";
import type { BusinessListItem, Category, Subcategory } from "@/types";

import { CategoryPickerSheet } from "./create/CategoryPickerSheet";
import { MapPickerSheet } from "./create/MapPickerSheet";
import { RulesSheet } from "./create/RulesSheet";
import {
  MAX_CUSTOM_TAGS,
  MAX_INTRO,
  MAX_PHOTOS,
  MAX_TAG_LENGTH,
  STEP_LABELS,
  TOTAL_STEPS,
  categoryPath,
  mainPhotoUrl,
  validateStep,
  type WizardData,
  type WizardPhoto,
} from "./create/types";

const EMPTY: WizardData = {
  title: "",
  description: "",
  category: null,
  subcategory: null,
  address: "",
  is24h: false,
  geo: null,
  photos: [],
  intro: "",
  shopPhone: "",
  instagram: "",
  licenseEnabled: false,
  standardTags: [],
  customTags: [],
};

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

function PinIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("h-4 w-4", className)}
      aria-hidden
    >
      <path d="M20 10c0 5-8 11-8 11S4 15 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </svg>
  );
}

function CheckIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2.2"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("h-4 w-4", className)}
      aria-hidden
    >
      <path d="M5 12l5 5L20 7" />
    </svg>
  );
}

function ImageIcon({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={cn("h-5 w-5", className)}
      aria-hidden
    >
      <rect x="3" y="4" width="18" height="16" rx="2.5" />
      <circle cx="8.5" cy="9.5" r="1.5" />
      <path d="M4 17l5-5 3.5 3.5L16 12l4 4" />
    </svg>
  );
}

function ChevronLeft({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      className={cn("h-4 w-4", className)}
      aria-hidden
    >
      <path d="M15 5l-7 7 7 7" />
    </svg>
  );
}

function PreviewRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex items-start justify-between gap-4 border-b border-slate-100 py-2.5 last:border-0">
      <span className="shrink-0 text-[11px] text-slate-400">{label}</span>
      <span className="min-w-0 text-left text-xs leading-6 text-slate-700">{children || "—"}</span>
    </div>
  );
}

export interface BusinessWizardProps {
  mode?: "create" | "edit";
  initialData?: WizardData;
  businessId?: string;
}

export default function CreateBusinessPage({
  mode = "create",
  initialData,
  businessId,
}: BusinessWizardProps = {}) {
  const user = useAuth((state) => state.user);
  const ready = useAuth((state) => state.ready);
  const navigate = useNavigate();
  const location = useLocation();
  const toast = useToast();
  const isEdit = mode === "edit";

  const [step, setStep] = useState(0);
  const [data, setData] = useState<WizardData>(initialData ?? EMPTY);
  const [acceptedRules, setAcceptedRules] = useState(isEdit);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [rulesOpen, setRulesOpen] = useState(false);
  const [customInput, setCustomInput] = useState("");
  const [uploading, setUploading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement | null>(null);

  const mine = useApi<{
    items: BusinessListItem[];
    limit: number;
    can_create: boolean;
    max_images: number;
  }>(["me", "businesses"], "/me/businesses", {
    enabled: ready && Boolean(user),
  });
  const maxPhotos = mine.data?.max_images ?? MAX_PHOTOS;

  useEffect(() => {
    if (step === 0) setError(null);
  }, [step]);

  if (!ready) {
    return (
      <div className="flex min-h-[50dvh] items-center justify-center text-brand-600">
        <Spinner />
      </div>
    );
  }
  if (!user) return <Navigate to={loginPath(returnPath(location))} replace />;

  if (mode === "create" && mine.data && mine.data.can_create === false) {
    return (
      <div className="mx-auto w-full max-w-lg px-4 py-10">
        <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-6 text-center">
          <p className="text-sm font-black text-slate-900">سقف ثبت کسب‌وکار</p>
          <p className="mt-2 text-xs leading-6 text-slate-500">
            شما به حد مجاز ثبت کسب‌وکار ({toFa(mine.data.limit)}) رسیده‌اید. برای ثبت کسب‌وکار
            جدید، ابتدا باید یکی از کسب‌وکارهای فعلی حذف شود.
          </p>
          <Link
            to="/me/businesses"
            className="mt-4 inline-block rounded-xl bg-brand-600 px-4 py-2 text-sm font-bold text-white"
          >
            بازگشت به کسب‌وکارهای من
          </Link>
        </div>
      </div>
    );
  }

  function patch(partial: Partial<WizardData>) {
    setData((current) => ({ ...current, ...partial }));
    setError(null);
  }

  function selectCategory(category: Category, subcategory: Subcategory | null) {
    patch({
      category,
      subcategory,
      standardTags: subcategory ? Array.from(new Set(subcategory.standard_tags)) : [],
    });
  }

  function next() {
    const message = validateStep(step, data, acceptedRules);
    if (message) {
      setError(message);
      return;
    }
    setError(null);
    if (step < TOTAL_STEPS - 1) {
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
    if (isEdit && !businessId) return;
    setSubmitting(true);
    setError(null);
    try {
      const tags = Array.from(new Set([...data.standardTags, ...data.customTags]));
      const mainImage = mainPhotoUrl(data.photos) || null;
      const saved = await api<BusinessListItem>(isEdit ? `/businesses/${businessId}` : "/businesses", {
        method: isEdit ? "PATCH" : "POST",
        body: JSON.stringify({
          name: data.title.trim(),
          description: data.description.trim() || null,
          category_id: data.category.id,
          subcategory_id: data.subcategory?.id ?? null,
          short_description: data.intro.trim(),
          phone_business: data.shopPhone.trim() || null,
          address: data.address.trim(),
          geo_lat: data.geo?.lat ?? null,
          geo_lng: data.geo?.lng ?? null,
          instagram: data.instagram.trim() || null,
          is_24h: data.is24h,
          profile_image_url: mainImage,
          images: data.photos.map((photo, index) => ({
            url: photo.url,
            is_main: photo.isMain,
            sort_order: index,
          })),
          tags,
        }),
      });
      if (!isEdit) {
        toast("کسب‌وکار ثبت شد و پس از تأیید مدیر نمایش داده می‌شود.");
      } else if (saved.status === "pending") {
        toast("تغییرات ذخیره شد و کسب‌وکار دوباره برای بررسی مدیر ارسال شد.");
      } else {
        toast("تغییرات ذخیره شد.");
      }
      navigate("/me/businesses");
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setSubmitting(false);
    }
  }

  async function uploadPictures(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;

    const remaining = maxPhotos - data.photos.length;
    if (remaining <= 0) {
      toast(`حداکثر ${toFa(maxPhotos)} تصویر می‌توانید اضافه کنید.`);
      return;
    }
    if (files.length > remaining) {
      toast(`فقط ${toFa(remaining)} تصویر دیگر قابل اضافه شدن است.`);
    }

    setUploading(true);
    let uploaded = 0;
    try {
      for (const file of files.slice(0, remaining)) {
        if (!file.type.startsWith("image/")) {
          toast("فقط تصویر مجاز است.");
          continue;
        }
        if (file.size > MAX_IMAGE_INPUT_BYTES) {
          toast("حجم تصویر باید کمتر از ۱۵ مگابایت باشد.");
          continue;
        }
        try {
          const prepared = await compressImageForUpload(file);
          if (prepared.size > MAX_IMAGE_UPLOAD_BYTES) {
            toast("حجم تصویر پس از بهینه‌سازی هنوز بیش از ۵ مگابایت است.");
            continue;
          }
          const form = new FormData();
          form.append("file", prepared);
          form.append("crop", "square");
          form.append("filter", "none");
          const result = await api<{ url: string }>("/uploads/image", {
            method: "POST",
            body: form,
          });
          setData((current) => {
            if (current.photos.length >= maxPhotos) return current;
            if (current.photos.some((photo) => photo.url === result.url)) return current;
            const nextPhoto: WizardPhoto = {
              url: result.url,
              isMain: current.photos.length === 0,
            };
            return { ...current, photos: [...current.photos, nextPhoto] };
          });
          uploaded += 1;
        } catch (uploadError) {
          toast(errorMessage(uploadError));
        }
      }
      if (uploaded > 0) {
        toast(
          uploaded === 1
            ? "تصویر بهینه‌سازی و بارگذاری شد."
            : `${toFa(uploaded)} تصویر بهینه‌سازی و بارگذاری شد.`,
        );
      }
    } finally {
      setUploading(false);
    }
  }

  function setMainPhoto(index: number) {
    patch({
      photos: data.photos.map((photo, photoIndex) => ({
        ...photo,
        isMain: photoIndex === index,
      })),
    });
  }

  function removePhoto(index: number) {
    const next = data.photos.filter((_, photoIndex) => photoIndex !== index);
    if (next.length > 0 && !next.some((photo) => photo.isMain)) {
      next[0] = { ...next[0], isMain: true };
    }
    patch({ photos: next });
  }

  function addCustomTag() {
    const name = customInput.trim().replace(/^#/, "");
    if (!name) return;
    if (name.length > MAX_TAG_LENGTH) {
      toast(`هر برچسب حداکثر ${toFa(MAX_TAG_LENGTH)} نویسه است.`);
      return;
    }
    const all = [...data.standardTags, ...data.customTags];
    if (all.includes(name)) {
      toast("این برچسب قبلاً اضافه شده است.");
      return;
    }
    if (data.customTags.length >= MAX_CUSTOM_TAGS) {
      toast(`حداکثر ${toFa(MAX_CUSTOM_TAGS)} برچسب دلخواه می‌توانید اضافه کنید.`);
      return;
    }
    patch({ customTags: [...data.customTags, name] });
    setCustomInput("");
  }

  const standardTags = data.subcategory?.standard_tags ?? [];
  const removedStandard = standardTags.filter(
    (tag) => !data.standardTags.includes(tag) && !data.customTags.includes(tag),
  );
  const allTags = [...data.standardTags, ...data.customTags];

  return (
    <div className="mx-auto flex min-h-[calc(100dvh-3.5rem)] w-full max-w-lg flex-col px-4 pb-0 pt-3">
      <header className="sticky top-14 z-20 -mx-4 mb-4 border-b border-slate-200 bg-slate-50 px-4 py-3">
        <div className="flex items-center justify-between gap-3">
          <span className="shrink-0 text-xs font-bold text-slate-500">
            گام {toFa(step + 1)} از {toFa(TOTAL_STEPS)}
          </span>
          <h1 className="truncate text-sm font-black text-slate-900">{STEP_LABELS[step]}</h1>
        </div>
        <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-slate-200">
          <div
            className="h-full rounded-full bg-brand-600 transition-all duration-300"
            style={{ width: `${((step + 1) / TOTAL_STEPS) * 100}%` }}
          />
        </div>
      </header>

      <div className="flex-1 pb-24">
      {step === 0 && (
        <section className="space-y-4">
          <div>
            <FieldLabel hint="حداقل ۳ حرف">نام کسب‌وکار</FieldLabel>
            <Input
              value={data.title}
              onChange={(event) => patch({ title: event.target.value })}
              placeholder="مثلاً کافه رستوران نومکس"
              maxLength={160}
            />
          </div>

          <div>
            <FieldLabel hint="حداقل ۱۰ نویسه">توضیحات</FieldLabel>
            <textarea
              rows={4}
              value={data.description}
              onChange={(event) => patch({ description: event.target.value })}
              placeholder="کسب‌وکار شما چه کاری انجام می‌دهد؟"
              maxLength={2000}
              className="w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
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
                    {categoryPath(data.category, data.subcategory)}
                  </span>
                ) : (
                  <span className="block text-sm text-slate-400">انتخاب دسته‌بندی</span>
                )}
              </span>
              {data.category ? (
                <CheckIcon className="shrink-0 text-brand-600" />
              ) : (
                <ChevronLeft className="shrink-0 text-slate-400" />
              )}
            </button>
          </div>
        </section>
      )}

      {step === 1 && (
        <section className="space-y-4">
          <div>
            <FieldLabel hint="از حساب شما">شماره تماس مالک</FieldLabel>
            <Input value={formatPhone(user.phone)} disabled dir="ltr" />
          </div>

          <div>
            <label className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-white p-3.5">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-brand-600"
                checked={data.is24h}
                onChange={(event) => patch({ is24h: event.target.checked })}
              />
              <span className="text-xs leading-6 text-slate-700">
                ⚡ کسب‌وکار من ۲۴ ساعته است (آماده‌ی خدمات اورژانسی)
              </span>
            </label>

            {data.is24h && (
              <div className="mt-2 rounded-xl border border-amber-200 bg-amber-50 p-3 text-[11px] leading-6 text-amber-800">
                <b>توجه:</b> با تیک‌زدن این گزینه، پس از تأیید مدیر کسب‌وکار شما با برچسب{" "}
                <b>⚡ اورژانسی</b> نمایش داده می‌شود و در فیلتر «اورژانسی» هم دیده می‌شود. یعنی
                مردم در هر ساعت شبانه‌روز انتظار پاسخ‌گویی از شما دارند. فقط در صورتی تیک بزنید که
                واقعاً ۲۴ ساعته پاسخگو هستید؛ در صورت گزارش خلاف، مدیر برچسب را حذف می‌کند.
              </div>
            )}
          </div>

          <div>
            <div className="mb-1.5 flex items-center justify-between gap-2">
              <FieldLabel>آدرس</FieldLabel>
              <Badge tone="sky" className="gap-1">
                <PinIcon className="h-3.5 w-3.5" />
                خوزستان ، بهبهان
              </Badge>
            </div>
            <textarea
              rows={2}
              value={data.address}
              onChange={(event) => patch({ address: event.target.value })}
              placeholder="خیابان، کوچه، پلاک..."
              maxLength={255}
              className="w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
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
                <PinIcon />
              </span>
              <span className="min-w-0 flex-1">
                <span className="block text-xs font-bold text-slate-800">
                  {data.geo ? "موقعیت انتخاب شد" : "انتخاب موقعیت روی نقشه"}
                </span>
                <span className="mt-0.5 block truncate text-[10px] text-slate-400" dir="ltr">
                  {data.geo
                    ? `${data.geo.lat.toFixed(5)}, ${data.geo.lng.toFixed(5)}`
                    : "با وارد کردن آدرس، محل کسب‌وکار را روی نقشه پیدا کنید."}
                </span>
              </span>
              <ChevronLeft className="shrink-0 text-slate-400" />
            </button>
          </div>
        </section>
      )}

      {step === 2 && (
        <section className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="text-xs font-bold text-slate-700">تصاویر کسب‌وکار</p>
                <p className="mt-1 text-[11px] leading-5 text-slate-400">
                  تا {toFa(maxPhotos)} تصویر؛ اولین تصویر یا تصویر ستاره‌دار در کارت و
                  جستجو نمایش داده می‌شود.
                </p>
              </div>
              <span className="shrink-0 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] text-slate-500">
                {toFa(data.photos.length)} از {toFa(maxPhotos)}
              </span>
            </div>

            <div className="mt-3 grid grid-cols-3 gap-2">
              {data.photos.map((photo, index) => (
                <div
                  key={`${photo.url}-${index}`}
                  className={cn(
                    "relative aspect-[4/3] overflow-hidden rounded-xl border-2 bg-slate-50",
                    photo.isMain ? "border-brand-400" : "border-transparent",
                  )}
                >
                  <img
                    src={photo.url}
                    alt={`تصویر ${toFa(index + 1)} کسب‌وکار`}
                    className="h-full w-full object-cover"
                  />
                  <button
                    type="button"
                    aria-label="حذف تصویر"
                    onClick={() => removePhoto(index)}
                    className="absolute left-1.5 top-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-slate-900/65 text-sm text-white backdrop-blur hover:bg-rose-600"
                  >
                    ×
                  </button>
                  {photo.isMain ? (
                    <span className="absolute inset-x-1 bottom-1 rounded-md bg-brand-600/90 py-1 text-center text-[9px] font-bold text-white backdrop-blur">
                      ★ تصویر اصلی
                    </span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => setMainPhoto(index)}
                      className="absolute inset-x-1 bottom-1 rounded-md bg-slate-900/65 py-1 text-[9px] font-medium text-white backdrop-blur hover:bg-brand-600"
                    >
                      تعیین به‌عنوان اصلی
                    </button>
                  )}
                </div>
              ))}

              {data.photos.length < maxPhotos && (
                <button
                  type="button"
                  disabled={uploading}
                  onClick={() => fileRef.current?.click()}
                  className="flex aspect-[4/3] flex-col items-center justify-center gap-1.5 rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 text-slate-400 transition-colors hover:border-brand-300 hover:bg-brand-50 hover:text-brand-600 disabled:opacity-60"
                >
                  {uploading ? (
                    <Spinner />
                  ) : (
                    <>
                      <ImageIcon className="h-5 w-5" />
                      <span className="text-[11px] font-medium">افزودن تصویر</span>
                    </>
                  )}
                </button>
              )}
            </div>

            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              multiple
              className="hidden"
              onChange={(event) => void uploadPictures(event)}
            />
            <p className="mt-3 text-[10px] leading-5 text-slate-400">
              انتخاب چند تصویر هم‌زمان ممکن است. برای تعیین تصویر اصلی، روی «تعیین به‌عنوان اصلی»
              همان تصویر بزنید.
            </p>
          </div>

          <details className="rounded-xl border border-dashed border-slate-300 bg-white">
            <summary className="flex cursor-pointer list-none items-center justify-between px-4 py-3 text-xs font-medium text-slate-600">
              مشخصات مالک (از حساب شما)
              <ChevronLeft className="text-slate-400" />
            </summary>
            <div className="space-y-2 border-t border-slate-100 px-4 py-3 text-xs">
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-400">نام</span>
                <span className="text-slate-700">{user.full_name || "ثبت نشده"}</span>
              </div>
              <div className="flex items-center justify-between gap-3">
                <span className="text-slate-400">شماره تماس</span>
                <span className="text-slate-700" dir="ltr">
                  {formatPhone(user.phone)}
                </span>
              </div>
            </div>
          </details>

          <div>
            <FieldLabel hint={`${toFa(data.intro.length)} از ${toFa(MAX_INTRO)} نویسه`}>
              معرفی کوتاه
            </FieldLabel>
            <textarea
              rows={3}
              value={data.intro}
              onChange={(event) => patch({ intro: event.target.value.slice(0, MAX_INTRO) })}
              placeholder="در یک جمله بگویید چه خدمتی ارائه می‌دهید."
              maxLength={MAX_INTRO}
              className="w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div>
            <FieldLabel hint="اختیاری">تلفن فروشگاه</FieldLabel>
            <Input
              value={data.shopPhone}
              onChange={(event) => patch({ shopPhone: normalizeDigits(event.target.value) })}
              placeholder="۰۹۱۲۳۴۵۶۷۸۹"
              inputMode="tel"
              dir="ltr"
              maxLength={11}
            />
          </div>

          <div>
            <FieldLabel hint="اختیاری">لینک اینستاگرام</FieldLabel>
            <Input
              value={data.instagram}
              onChange={(event) => patch({ instagram: event.target.value })}
              placeholder="https://instagram.com/yourpage"
              dir="ltr"
              inputMode="url"
            />
          </div>

          <div>
            <label className="flex items-start gap-2.5 rounded-xl border border-slate-200 bg-white p-3.5">
              <input
                type="checkbox"
                className="mt-0.5 h-4 w-4 accent-brand-600"
                checked={data.licenseEnabled}
                onChange={(event) => patch({ licenseEnabled: event.target.checked })}
              />
              <span className="text-xs leading-6 text-slate-700">پروانه کسب دارم</span>
            </label>

            {data.licenseEnabled && (
              <div className="mt-2 space-y-3 rounded-xl border border-dashed border-slate-300 bg-white p-3.5 opacity-70">
                <p className="rounded-lg bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-700">
                  این بخش به‌زودی فعال می‌شود؛ فعلاً نیازی به وارد کردن اطلاعات پروانه نیست.
                </p>
                <div>
                  <FieldLabel>شماره / شناسه پروانه</FieldLabel>
                  <Input disabled placeholder="شماره یا شناسه پروانه کسب" />
                </div>
                <div>
                  <FieldLabel>تصویر پروانه کسب</FieldLabel>
                  <div className="flex h-20 items-center justify-center rounded-xl border-2 border-dashed border-slate-200 bg-slate-50 text-[11px] text-slate-400">
                    بارگذاری تصویر به‌زودی
                  </div>
                </div>
              </div>
            )}
          </div>
        </section>
      )}

      {step === 3 && (
        <section className="space-y-4">
          <p className="text-xs leading-6 text-slate-500">
            خدماتی که ارائه می‌دهید را انتخاب کنید. برچسب‌های پیشنهادی را می‌توانید حذف کنید.
          </p>

          <div className="rounded-2xl border border-slate-200 bg-white p-3.5">
            <div className="flex items-center justify-between">
              <p className="text-xs font-bold text-slate-700">خدمات انتخاب‌شده</p>
              <span className="text-[10px] text-slate-400">
                {toFa(data.standardTags.length)} خدمت
              </span>
            </div>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {allTags.length === 0 && (
                <p className="py-2 text-[11px] text-slate-400">هنوز خدمتی انتخاب نشده است.</p>
              )}
              {data.standardTags.map((tag) => (
                <span
                  key={`standard-${tag}`}
                  className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2.5 py-1 text-[11px] font-medium text-brand-700"
                >
                  {tag}
                  <button
                    type="button"
                    aria-label={`حذف ${tag}`}
                    onClick={() =>
                      patch({ standardTags: data.standardTags.filter((item) => item !== tag) })
                    }
                    className="text-brand-500 hover:text-brand-700"
                  >
                    ×
                  </button>
                </span>
              ))}
              {data.customTags.map((tag) => (
                <span
                  key={`custom-${tag}`}
                  className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] font-medium text-amber-700"
                >
                  {tag}
                  <button
                    type="button"
                    aria-label={`حذف ${tag}`}
                    onClick={() =>
                      patch({ customTags: data.customTags.filter((item) => item !== tag) })
                    }
                    className="text-amber-500 hover:text-amber-700"
                  >
                    ×
                  </button>
                </span>
              ))}
            </div>
          </div>

          {removedStandard.length > 0 && (
            <div>
              <p className="mb-1.5 text-[11px] text-slate-400">افزودن دوباره پیشنهادها</p>
              <div className="flex flex-wrap gap-1.5">
                {removedStandard.map((tag) => (
                  <button
                    key={`removed-${tag}`}
                    type="button"
                    onClick={() => patch({ standardTags: [...data.standardTags, tag] })}
                    className="rounded-full border border-dashed border-slate-300 bg-white px-2.5 py-1 text-[11px] text-slate-500 hover:border-brand-300 hover:text-brand-600"
                  >
                    + {tag}
                  </button>
                ))}
              </div>
            </div>
          )}

          <div>
            <FieldLabel hint={`${toFa(data.customTags.length)} از ${toFa(MAX_CUSTOM_TAGS)}`}>
              برچسب دلخواه
            </FieldLabel>
            <div className="flex gap-2">
              <Input
                value={customInput}
                onChange={(event) => setCustomInput(event.target.value.slice(0, MAX_TAG_LENGTH))}
                onKeyDown={(event) => {
                  if (event.key === "Enter") {
                    event.preventDefault();
                    addCustomTag();
                  }
                }}
                placeholder="مثلاً تعمیر یخچال"
                maxLength={MAX_TAG_LENGTH}
              />
              <Button type="button" variant="outline" onClick={addCustomTag} className="shrink-0">
                افزودن
              </Button>
            </div>
            <p className="mt-1.5 text-[10px] text-slate-400">
              حداکثر {toFa(MAX_CUSTOM_TAGS)} برچسب دلخواه، هر کدام تا {toFa(MAX_TAG_LENGTH)} نویسه.
            </p>
          </div>
        </section>
      )}

      {step === 4 && (
        <section className="space-y-4">
          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="mb-1 flex items-center justify-between">
              <h2 className="text-xs font-black text-slate-900">کسب‌وکار</h2>
              <button type="button" onClick={() => setStep(0)} className="text-[11px] text-brand-600">
                ویرایش
              </button>
            </div>
            <PreviewRow label="نام">{data.title}</PreviewRow>
            <PreviewRow label="دسته‌بندی">{categoryPath(data.category, data.subcategory)}</PreviewRow>
            <PreviewRow label="توضیحات">
              <span className="line-clamp-3">{data.description}</span>
            </PreviewRow>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="mb-1 flex items-center justify-between">
              <h2 className="text-xs font-black text-slate-900">راه ارتباطی و آدرس</h2>
              <button type="button" onClick={() => setStep(1)} className="text-[11px] text-brand-600">
                ویرایش
              </button>
            </div>
            <PreviewRow label="آدرس">{data.address}</PreviewRow>
            <PreviewRow label="۲۴ ساعته">{data.is24h ? "بله ⚡" : "خیر"}</PreviewRow>
            <PreviewRow label="تلفن فروشگاه">
              {data.shopPhone ? <span dir="ltr">{data.shopPhone}</span> : null}
            </PreviewRow>
            <PreviewRow label="موقعیت">
              {data.geo ? (
                <span dir="ltr">
                  {data.geo.lat.toFixed(5)}, {data.geo.lng.toFixed(5)}
                </span>
              ) : (
                "ثبت نشده"
              )}
            </PreviewRow>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="mb-1 flex items-center justify-between">
              <h2 className="text-xs font-black text-slate-900">اطلاعات تکمیلی</h2>
              <button type="button" onClick={() => setStep(2)} className="text-[11px] text-brand-600">
                ویرایش
              </button>
            </div>
            {data.photos.length > 0 && (
              <div className="mb-3">
                <img
                  src={mainPhotoUrl(data.photos)}
                  alt="تصویر اصلی کسب‌وکار"
                  className="h-32 w-full rounded-xl object-cover"
                />
                {data.photos.length > 1 && (
                  <div className="mt-2 flex gap-1.5 overflow-x-auto pb-1">
                    {data.photos.map((photo, index) => (
                      <img
                        key={`preview-${photo.url}-${index}`}
                        src={photo.url}
                        alt={`تصویر ${toFa(index + 1)}`}
                        className={cn(
                          "h-12 w-12 shrink-0 rounded-lg object-cover",
                          photo.isMain && "ring-2 ring-brand-500",
                        )}
                      />
                    ))}
                  </div>
                )}
              </div>
            )}
            <PreviewRow label="تعداد تصاویر">{toFa(data.photos.length)} تصویر</PreviewRow>
            <PreviewRow label="معرفی">{data.intro}</PreviewRow>
            <PreviewRow label="اینستاگرام">
              {data.instagram ? (
                <span className="break-all" dir="ltr">
                  {data.instagram}
                </span>
              ) : null}
            </PreviewRow>
            <PreviewRow label="مالک">{user.full_name || formatPhone(user.phone)}</PreviewRow>
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-xs font-black text-slate-900">خدمات</h2>
              <button type="button" onClick={() => setStep(3)} className="text-[11px] text-brand-600">
                ویرایش
              </button>
            </div>
            {allTags.length > 0 ? (
              <div className="flex flex-wrap gap-1.5">
                {allTags.map((tag) => (
                  <span
                    key={tag}
                    className="rounded-full bg-slate-100 px-2.5 py-1 text-[11px] text-slate-600"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            ) : (
              <p className="text-xs text-slate-400">خدمتی انتخاب نشده است.</p>
            )}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-4">
            <div className="flex items-start gap-2.5">
              <input
                id="accept-rules"
                type="checkbox"
                className="mt-0.5 h-4 w-4 shrink-0 accent-brand-600"
                checked={acceptedRules}
                disabled={isEdit}
                onChange={(event) => {
                  setAcceptedRules(event.target.checked);
                  setError(null);
                }}
              />
              <div className="text-[11px] leading-6 text-slate-600">
                <label htmlFor="accept-rules" className={cn(isEdit ? "cursor-default" : "cursor-pointer")}>
                  {isEdit
                    ? "قوانین نومکس پذیرفته شده است."
                    : "قوانین نومکس را خوانده‌ام و می‌پذیرم."}
                </label>{" "}
                <button
                  type="button"
                  onClick={() => setRulesOpen(true)}
                  className="font-bold text-brand-600 underline-offset-2 hover:underline"
                >
                  مشاهده قوانین
                </button>
              </div>
            </div>
          </div>
        </section>
      )}
      </div>

      <div className="sticky bottom-0 z-30 -mx-4 mt-auto border-t border-slate-200 bg-white px-4 pb-[calc(env(safe-area-inset-bottom,0px)+0.75rem)] pt-4">
        {error && (
          <div className="mb-2">
            <ErrorText>{error}</ErrorText>
          </div>
        )}
        <div className="flex gap-2">
          {step > 0 && (
            <Button type="button" variant="outline" className="flex-1" onClick={back}>
              مرحله قبل
            </Button>
          )}
          <Button type="button" className="flex-1" loading={submitting} onClick={next}>
            {step === TOTAL_STEPS - 1
              ? isEdit
                ? "ذخیره تغییرات"
                : "ثبت کسب‌وکار"
              : "مرحله بعد"}
          </Button>
        </div>
      </div>

      <CategoryPickerSheet
        open={categoryOpen}
        onClose={() => setCategoryOpen(false)}
        selected={data.category}
        selectedSubcategory={data.subcategory}
        onSelect={selectCategory}
      />
      <MapPickerSheet
        open={mapOpen}
        address={data.address}
        value={data.geo}
        onClose={() => setMapOpen(false)}
        onConfirm={(address, geo) => {
          patch({ address: address || data.address, geo });
          setMapOpen(false);
        }}
      />
      <RulesSheet open={rulesOpen} onClose={() => setRulesOpen(false)} />
    </div>
  );
}
