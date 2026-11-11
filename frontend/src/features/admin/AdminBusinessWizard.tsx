import { useEffect, useRef, useState } from "react";

import { Button, Spinner } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { formatPhone } from "@/lib/format";
import {
  MAX_IMAGE_INPUT_BYTES,
  MAX_IMAGE_UPLOAD_BYTES,
  compressImageForUpload,
} from "@/lib/image";
import { useApi } from "@/lib/query";
import type { Category, Coordinates, Subcategory } from "@/types";
import { CategoryPickerSheet } from "@/features/business/create/CategoryPickerSheet";
import { MapPickerSheet } from "@/features/business/create/MapPickerSheet";
import { MAX_PHOTOS } from "@/features/business/create/types";

import { AdminModal } from "./AdminModal";

type BusinessStatus = "pending" | "approved" | "rejected";

interface OwnerOption {
  id: string;
  phone: string;
  full_name?: string | null;
  role?: string;
  is_verified?: boolean;
}

interface CategoryRef {
  id: number;
  slug: string;
  name: string;
  icon?: string;
}

export interface AdminBusinessDetail {
  id: string;
  name: string;
  slug: string;
  status: BusinessStatus;
  is_verified: boolean;
  is_24h: boolean;
  short_description: string;
  description?: string | null;
  address: string;
  phone_business?: string | null;
  instagram?: string | null;
  geo?: { lat: number; lng: number } | null;
  category: CategoryRef | null;
  subcategory: CategoryRef | null;
  profile_image_url?: string | null;
  rejection_reason?: string | null;
  owner: OwnerOption | null;
  images?: Array<{ url: string; is_main: boolean; sort_order: number }>;
  tags?: string[];
}

interface Photo {
  url: string;
  isMain: boolean;
}

interface WizardState {
  owner: OwnerOption | null;
  name: string;
  description: string;
  short_description: string;
  category: Category | null;
  subcategory: Subcategory | null;
  address: string;
  geo: Coordinates | null;
  phone_business: string;
  instagram: string;
  is_24h: boolean;
  photos: Photo[];
  tags: string[];
  is_verified: boolean;
  status: BusinessStatus;
  rejection_reason: string;
}

const STEPS = [
  "مالک کسب‌وکار",
  "اطلاعات کسب‌وکار",
  "راه ارتباطی و آدرس",
  "تصاویر و خدمات",
  "وضعیت و تأیید",
] as const;

const IRAN_PHONE = /^0\d{10}$/;

function asCategory(category: CategoryRef | null): Category | null {
  return category ? { ...category, sort_order: 0, subcategory_count: 0, icon: category.icon ?? "" } : null;
}

function asSubcategory(subcategory: CategoryRef | null, category: Category | null): Subcategory | null {
  return subcategory && category
    ? {
        ...subcategory,
        category_id: category.id,
        sort_order: 0,
        icon: subcategory.icon ?? "",
        standard_tags: [],
      }
    : null;
}

function initialState(business: AdminBusinessDetail | null): WizardState {
  const category = asCategory(business?.category ?? null);
  const images = business?.images?.length
    ? [...business.images].sort((a, b) => a.sort_order - b.sort_order)
    : business?.profile_image_url
      ? [{ url: business.profile_image_url, is_main: true, sort_order: 0 }]
      : [];
  const mainUrl = images.find((image) => image.is_main)?.url ?? images[0]?.url;
  return {
    owner: business?.owner ?? null,
    name: business?.name ?? "",
    description: business?.description ?? "",
    short_description: business?.short_description ?? "",
    category,
    subcategory: asSubcategory(business?.subcategory ?? null, category),
    address: business?.address ?? "",
    geo: business?.geo ?? null,
    phone_business: business?.phone_business ?? "",
    instagram: business?.instagram ?? "",
    is_24h: business?.is_24h ?? false,
    photos: images.map((image) => ({ url: image.url, isMain: image.url === mainUrl })),
    tags: business?.tags ?? [],
    is_verified: business?.is_verified ?? false,
    status: business?.status ?? "pending",
    rejection_reason: business?.rejection_reason ?? "",
  };
}

function Field({ label, hint, children }: { label: string; hint?: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1.5">
      <span className="flex items-baseline justify-between gap-3 text-xs font-bold text-slate-700">
        {label}
        {hint && <span className="font-normal text-slate-400">{hint}</span>}
      </span>
      {children}
    </label>
  );
}

export function AdminBusinessWizard({
  business,
  saving,
  onClose,
  onSubmit,
}: {
  business: AdminBusinessDetail | null;
  saving: boolean;
  onClose: () => void;
  onSubmit: (payload: Record<string, unknown>) => void;
}) {
  const toast = useToast();
  const isEdit = business !== null;
  const [step, setStep] = useState(0);
  const [state, setState] = useState<WizardState>(() => initialState(business));
  const [error, setError] = useState<string | null>(null);
  const [categoryOpen, setCategoryOpen] = useState(false);
  const [mapOpen, setMapOpen] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [customTag, setCustomTag] = useState("");
  const [newOwnerOpen, setNewOwnerOpen] = useState(false);
  const [newOwner, setNewOwner] = useState({ phone: "", full_name: "", national_id: "" });
  const [creatingOwner, setCreatingOwner] = useState(false);
  const [ownerQuery, setOwnerQuery] = useState("");
  const fileRef = useRef<HTMLInputElement | null>(null);

  const owners = useApi<{ items: OwnerOption[] }>(
    ["admin", "business-owners", ownerQuery],
    `/admin/businesses/owners?q=${encodeURIComponent(ownerQuery)}&limit=12`,
    { enabled: step === 0 && !state.owner, staleTime: 30_000 },
  );
  const subcategories = useApi<{ items: Subcategory[] }>(
    ["categories", "all-subcategories"],
    "/categories/subcategories",
    { enabled: isEdit || state.category !== null },
  );

  useEffect(() => {
    if (step === 0) setError(null);
  }, [step]);

  function patch(partial: Partial<WizardState>) {
    setState((current) => ({ ...current, ...partial }));
    setError(null);
  }

  const suggestedTags =
    subcategories.data?.items.find((item) => item.id === state.subcategory?.id)?.standard_tags ?? [];

  function validate(current: number): string | null {
    if (current === 0 && !state.owner) return "مالک کسب‌وکار را انتخاب یا ثبت کنید.";
    if (current === 1) {
      if (state.name.trim().length < 3) return "نام کسب‌وکار را وارد کنید (حداقل ۳ حرف).";
      if (!state.category) return "دسته‌بندی کسب‌وکار را انتخاب کنید.";
    }
    if (current === 2) {
      if (state.address.trim().length < 5) return "آدرس کسب‌وکار را وارد کنید.";
      if (state.phone_business.trim() && !IRAN_PHONE.test(state.phone_business.trim())) {
        return "تلفن کسب‌وکار باید ۱۱ رقم و با ۰ شروع شود.";
      }
    }
    if (current === 4 && state.status === "rejected" && !state.rejection_reason.trim()) {
      return "دلیل رد کسب‌وکار را وارد کنید.";
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
      return;
    }
    submit();
  }

  function submit() {
    if (!state.owner) return;
    const mainPhoto = state.photos.find((photo) => photo.isMain)?.url ?? state.photos[0]?.url ?? null;
    onSubmit({
      owner_id: state.owner.id,
      name: state.name.trim(),
      category_id: state.category?.id ?? null,
      subcategory_id: state.subcategory?.id ?? null,
      short_description: state.short_description.trim().slice(0, 120),
      description: state.description.trim() || null,
      phone_business: state.phone_business.trim() || null,
      address: state.address.trim(),
      geo_lat: state.geo?.lat ?? null,
      geo_lng: state.geo?.lng ?? null,
      instagram: state.instagram.trim() || null,
      is_24h: state.is_24h,
      is_verified: state.is_verified,
      status: state.status,
      rejection_reason: state.status === "rejected" ? state.rejection_reason.trim() || null : null,
      profile_image_url: mainPhoto,
      images: state.photos.map((photo, index) => ({
        url: photo.url,
        is_main: photo.isMain,
        sort_order: index,
      })),
      tags: state.tags,
    });
  }

  async function createOwner() {
    if (!newOwner.phone.trim()) {
      setError("شماره موبایل مالک را وارد کنید.");
      return;
    }
    setCreatingOwner(true);
    try {
      const owner = await api<OwnerOption>("/admin/businesses/owners", {
        method: "POST",
        body: JSON.stringify({
          phone: newOwner.phone.trim(),
          full_name: newOwner.full_name.trim() || null,
          national_id: newOwner.national_id.trim() || null,
        }),
      });
      patch({ owner });
      setNewOwner({ phone: "", full_name: "", national_id: "" });
      setNewOwnerOpen(false);
      toast("مالک جدید ساخته و انتخاب شد.");
    } catch (createError) {
      setError(errorMessage(createError));
    } finally {
      setCreatingOwner(false);
    }
  }

  async function uploadPhotos(event: React.ChangeEvent<HTMLInputElement>) {
    const files = Array.from(event.target.files ?? []);
    event.target.value = "";
    if (!files.length) return;
    const remaining = MAX_PHOTOS - state.photos.length;
    if (remaining <= 0) {
      toast(`حداکثر ${MAX_PHOTOS} تصویر می‌توانید اضافه کنید.`);
      return;
    }
    setUploading(true);
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
          const result = await api<{ url: string }>("/uploads/image", { method: "POST", body: form });
          setState((current) => {
            if (current.photos.length >= MAX_PHOTOS) return current;
            if (current.photos.some((photo) => photo.url === result.url)) return current;
            return {
              ...current,
              photos: [
                ...current.photos,
                { url: result.url, isMain: current.photos.length === 0 },
              ],
            };
          });
        } catch (uploadError) {
          toast(errorMessage(uploadError));
        }
      }
    } finally {
      setUploading(false);
    }
  }

  function setMainPhoto(index: number) {
    patch({
      photos: state.photos.map((photo, photoIndex) => ({
        ...photo,
        isMain: photoIndex === index,
      })),
    });
  }

  function removePhoto(index: number) {
    const photos = state.photos.filter((_, photoIndex) => photoIndex !== index);
    patch({
      photos: photos.map((photo, photoIndex) =>
        photoIndex === 0 && !photos.some((item) => item.isMain)
          ? { ...photo, isMain: true }
          : photo,
      ),
    });
  }

  function addCustomTag() {
    const tag = customTag.trim().replace(/^#/, "");
    if (!tag) return;
    if (state.tags.includes(tag)) {
      toast("این برچسب قبلاً اضافه شده است.");
      return;
    }
    patch({ tags: [...state.tags, tag] });
    setCustomTag("");
  }

  return (
    <AdminModal title={isEdit ? "ویرایش کسب‌وکار" : "افزودن کسب‌وکار"} onClose={onClose}>
      <div className="space-y-4">
        <div>
          <div className="mb-2 flex items-center justify-between gap-3">
            <span className="text-[11px] font-bold text-slate-500">
              گام {step + 1} از {STEPS.length}
            </span>
            <span className="text-sm font-black text-slate-900">{STEPS[step]}</span>
          </div>
          <div className="h-1.5 overflow-hidden rounded-full bg-slate-100">
            <div
              className="h-full rounded-full bg-brand-600 transition-all duration-300"
              style={{ width: `${((step + 1) / STEPS.length) * 100}%` }}
            />
          </div>
        </div>

        {step === 0 && (
          <section className="space-y-3">
            {state.owner ? (
              <div className="flex items-center justify-between gap-3 rounded-xl border border-brand-200 bg-brand-50/60 px-3 py-3">
                <div className="min-w-0">
                  <p className="truncate text-sm font-bold text-slate-900">
                    {state.owner.full_name || "بدون نام"}
                  </p>
                  <p className="mt-0.5 text-xs text-slate-500" dir="ltr">
                    {formatPhone(state.owner.phone)}
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => patch({ owner: null })}
                  className="shrink-0 text-xs font-medium text-rose-600 hover:underline"
                >
                  تغییر مالک
                </button>
              </div>
            ) : (
              <>
                <div className="space-y-1.5">
                  <div className="flex items-baseline justify-between gap-3 text-xs font-bold text-slate-700">
                    انتخاب از مالکان / مشتریان
                    <span className="font-normal text-slate-400">با نام یا شماره جستجو کنید</span>
                  </div>
                  <Input
                    value={ownerQuery}
                    onChange={(event) => setOwnerQuery(event.target.value)}
                    placeholder="جستجوی نام یا شماره موبایل…"
                  />
                  <div className="mt-2 max-h-56 space-y-1 overflow-y-auto rounded-xl border border-slate-200 bg-white p-1">
                    {owners.isLoading && (
                      <div className="flex justify-center py-6 text-brand-600">
                        <Spinner />
                      </div>
                    )}
                    {owners.data?.items.map((owner) => (
                      <button
                        key={owner.id}
                        type="button"
                        onClick={() => patch({ owner })}
                        className="flex w-full items-center justify-between gap-3 rounded-lg px-3 py-2 text-right hover:bg-slate-50"
                      >
                        <span className="min-w-0">
                          <span className="block truncate text-xs font-bold text-slate-800">
                            {owner.full_name || "بدون نام"}
                          </span>
                          <span className="mt-0.5 block text-[11px] text-slate-400" dir="ltr">
                            {formatPhone(owner.phone)}
                          </span>
                        </span>
                        <span className="shrink-0 rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">
                          {owner.role === "owner" ? "مالک" : "مشتری"}
                        </span>
                      </button>
                    ))}
                    {!owners.isLoading && !owners.data?.items.length && (
                      <p className="px-3 py-4 text-center text-xs text-slate-400">
                        کاربری پیدا نشد. مالک جدید بسازید.
                      </p>
                    )}
                  </div>
                </div>
                <button
                  type="button"
                  onClick={() => setNewOwnerOpen((open) => !open)}
                  className="text-xs font-bold text-brand-600 hover:underline"
                >
                  {newOwnerOpen ? "بستن فرم مالک جدید" : "+ ساخت مالک جدید"}
                </button>
                {newOwnerOpen && (
                  <div className="space-y-2 rounded-xl border border-dashed border-slate-300 bg-slate-50/60 p-3">
                    <Field label="شماره موبایل">
                      <Input
                        dir="ltr"
                        inputMode="tel"
                        placeholder="0912 345 6789"
                        value={newOwner.phone}
                        onChange={(event) =>
                          setNewOwner((current) => ({ ...current, phone: event.target.value }))
                        }
                      />
                    </Field>
                    <Field label="نام نمایشی" hint="اختیاری">
                      <Input
                        value={newOwner.full_name}
                        onChange={(event) =>
                          setNewOwner((current) => ({ ...current, full_name: event.target.value }))
                        }
                      />
                    </Field>
                    <Field label="کد ملی" hint="اختیاری">
                      <Input
                        dir="ltr"
                        inputMode="numeric"
                        maxLength={10}
                        value={newOwner.national_id}
                        onChange={(event) =>
                          setNewOwner((current) => ({ ...current, national_id: event.target.value }))
                        }
                      />
                    </Field>
                    <Button
                      type="button"
                      size="sm"
                      loading={creatingOwner}
                      onClick={() => void createOwner()}
                    >
                      ساخت و انتخاب مالک
                    </Button>
                  </div>
                )}
              </>
            )}
          </section>
        )}

        {step === 1 && (
          <section className="space-y-3">
            <Field label="نام کسب‌وکار">
              <Input
                value={state.name}
                maxLength={160}
                onChange={(event) => patch({ name: event.target.value })}
              />
            </Field>
            <div className="space-y-1.5">
              <span className="block text-xs font-bold text-slate-700">دسته‌بندی</span>
              <button
                type="button"
                onClick={() => setCategoryOpen(true)}
                className={cn(
                  "flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-right",
                  state.category
                    ? "border-brand-300 bg-brand-50"
                    : "border-dashed border-slate-300 bg-white",
                )}
              >
                <span className="min-w-0 truncate text-sm">
                  {state.category
                    ? `${state.category.name}${state.subcategory ? ` > ${state.subcategory.name}` : ""}`
                    : "انتخاب دسته‌بندی…"}
                </span>
                <span className="shrink-0 text-xs text-brand-600">تغییر</span>
              </button>
            </div>
            <Field label="معرفی کوتاه" hint={`${state.short_description.length} از ۱۲۰`}>
              <Input
                value={state.short_description}
                maxLength={120}
                onChange={(event) => patch({ short_description: event.target.value })}
              />
            </Field>
            <Field label="توضیحات">
              <textarea
                rows={4}
                maxLength={2000}
                value={state.description}
                onChange={(event) => patch({ description: event.target.value })}
                className="w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </Field>
          </section>
        )}

        {step === 2 && (
          <section className="space-y-3">
            <Field label="آدرس">
              <textarea
                rows={2}
                maxLength={255}
                value={state.address}
                onChange={(event) => patch({ address: event.target.value })}
                className="w-full resize-none rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
              />
            </Field>
            <button
              type="button"
              onClick={() => setMapOpen(true)}
              className={cn(
                "flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2.5 text-right text-sm",
                state.geo ? "border-brand-300 bg-brand-50" : "border-dashed border-slate-300 bg-white",
              )}
            >
              <span>{state.geo ? "موقعیت انتخاب شده" : "انتخاب موقعیت روی نقشه"}</span>
              <span className="text-xs text-slate-500" dir="ltr">
                {state.geo ? `${state.geo.lat.toFixed(5)}, ${state.geo.lng.toFixed(5)}` : "اختیاری"}
              </span>
            </button>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="تلفن کسب‌وکار" hint="اختیاری">
                <Input
                  dir="ltr"
                  inputMode="tel"
                  maxLength={11}
                  value={state.phone_business}
                  onChange={(event) => patch({ phone_business: event.target.value })}
                />
              </Field>
              <Field label="اینستاگرام" hint="اختیاری">
                <Input
                  dir="ltr"
                  value={state.instagram}
                  onChange={(event) => patch({ instagram: event.target.value })}
                />
              </Field>
            </div>
            <label className="flex items-center gap-2 rounded-xl border border-slate-200 bg-white px-3 py-2.5 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={state.is_24h}
                onChange={(event) => patch({ is_24h: event.target.checked })}
                className="h-4 w-4 accent-brand-600"
              />
              کسب‌وکار ۲۴ ساعته است
            </label>
          </section>
        )}

        {step === 3 && (
          <section className="space-y-4">
            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-bold text-slate-700">تصاویر کسب‌وکار</p>
                <span className="text-[10px] text-slate-400">
                  {state.photos.length} از {MAX_PHOTOS}
                </span>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-4">
                {state.photos.map((photo, index) => (
                  <div
                    key={`${photo.url}-${index}`}
                    className={cn(
                      "relative aspect-[4/3] overflow-hidden rounded-lg border-2 bg-slate-50",
                      photo.isMain ? "border-brand-400" : "border-transparent",
                    )}
                  >
                    <img src={photo.url} alt="" className="h-full w-full object-cover" />
                    <button
                      type="button"
                      aria-label="حذف تصویر"
                      onClick={() => removePhoto(index)}
                      className="absolute left-1 top-1 flex h-6 w-6 items-center justify-center rounded-full bg-slate-900/70 text-white hover:bg-rose-600"
                    >
                      ×
                    </button>
                    {photo.isMain ? (
                      <span className="absolute inset-x-1 bottom-1 rounded bg-brand-600/90 py-0.5 text-center text-[9px] font-bold text-white">
                        ★ اصلی
                      </span>
                    ) : (
                      <button
                        type="button"
                        onClick={() => setMainPhoto(index)}
                        className="absolute inset-x-1 bottom-1 rounded bg-slate-900/70 py-0.5 text-[9px] text-white hover:bg-brand-600"
                      >
                        اصلی شود
                      </button>
                    )}
                  </div>
                ))}
                {state.photos.length < MAX_PHOTOS && (
                  <button
                    type="button"
                    disabled={uploading}
                    onClick={() => fileRef.current?.click()}
                    className="flex aspect-[4/3] flex-col items-center justify-center gap-1 rounded-lg border-2 border-dashed border-slate-300 bg-slate-50 text-[11px] text-slate-400 hover:border-brand-300 hover:text-brand-600"
                  >
                    {uploading ? <Spinner /> : "+ تصویر"}
                  </button>
                )}
              </div>
              <input
                ref={fileRef}
                type="file"
                accept="image/*"
                multiple
                className="hidden"
                onChange={(event) => void uploadPhotos(event)}
              />
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-3">
              <p className="text-xs font-bold text-slate-700">خدمات و برچسب‌ها</p>
              {suggestedTags.length > 0 && (
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {suggestedTags.map((tag) => {
                    const active = state.tags.includes(tag);
                    return (
                      <button
                        key={tag}
                        type="button"
                        onClick={() =>
                          patch({
                            tags: active
                              ? state.tags.filter((item) => item !== tag)
                              : [...state.tags, tag],
                          })
                        }
                        className={cn(
                          "rounded-full border px-2.5 py-1 text-[11px]",
                          active
                            ? "border-brand-600 bg-brand-600 text-white"
                            : "border-slate-200 bg-white text-slate-600",
                        )}
                      >
                        {tag}
                      </button>
                    );
                  })}
                </div>
              )}
              <div className="mt-2 flex flex-wrap gap-1.5">
                {state.tags
                  .filter((tag) => !suggestedTags.includes(tag))
                  .map((tag) => (
                    <span
                      key={tag}
                      className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[11px] text-amber-700"
                    >
                      {tag}
                      <button
                        type="button"
                        aria-label={`حذف ${tag}`}
                        onClick={() => patch({ tags: state.tags.filter((item) => item !== tag) })}
                      >
                        ×
                      </button>
                    </span>
                  ))}
              </div>
              <div className="mt-2 flex gap-2">
                <Input
                  value={customTag}
                  maxLength={30}
                  onChange={(event) => setCustomTag(event.target.value)}
                  onKeyDown={(event) => {
                    if (event.key === "Enter") {
                      event.preventDefault();
                      addCustomTag();
                    }
                  }}
                  placeholder="برچسب دلخواه…"
                />
                <Button type="button" variant="outline" className="shrink-0" onClick={addCustomTag}>
                  افزودن
                </Button>
              </div>
            </div>
          </section>
        )}

        {step === 4 && (
          <section className="space-y-3">
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label="وضعیت انتشار">
                <select
                  value={state.status}
                  onChange={(event) => patch({ status: event.target.value as BusinessStatus })}
                  className="h-11 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-800"
                >
                  <option value="pending">در انتظار تأیید</option>
                  <option value="approved">تأییدشده</option>
                  <option value="rejected">ردشده</option>
                </select>
              </Field>
              <label className="flex items-center gap-2 self-end rounded-xl border border-slate-200 bg-white px-3 py-3 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={state.is_verified}
                  onChange={(event) => patch({ is_verified: event.target.checked })}
                  className="h-4 w-4 accent-brand-600"
                />
                مجوز تأییدشده
              </label>
            </div>
            {state.status === "rejected" && (
              <Field label="دلیل رد">
                <Input
                  value={state.rejection_reason}
                  maxLength={255}
                  onChange={(event) => patch({ rejection_reason: event.target.value })}
                />
              </Field>
            )}
            <div className="rounded-xl border border-slate-200 bg-slate-50/60 p-3 text-xs leading-6 text-slate-600">
              <p>
                <b className="text-slate-800">{state.name || "بدون نام"}</b>
                {state.category ? ` — ${state.category.name}` : ""}
              </p>
              <p>مالک: {state.owner?.full_name || (state.owner ? formatPhone(state.owner.phone) : "—")}</p>
              <p>آدرس: {state.address || "—"}</p>
              <p>
                تصاویر: {state.photos.length} — برچسب‌ها: {state.tags.length}
              </p>
            </div>
          </section>
        )}

        {error && <p className="text-xs leading-5 text-rose-600">{error}</p>}

        <div className="flex gap-2 border-t border-slate-100 pt-3">
          {step > 0 && (
            <Button type="button" variant="outline" className="flex-1" onClick={() => setStep((s) => s - 1)}>
              مرحله قبل
            </Button>
          )}
          <Button type="button" className="flex-1" loading={saving} onClick={next}>
            {step === STEPS.length - 1 ? (isEdit ? "ذخیره تغییرات" : "ساخت کسب‌وکار") : "مرحله بعد"}
          </Button>
        </div>
      </div>

      <CategoryPickerSheet
        open={categoryOpen}
        onClose={() => setCategoryOpen(false)}
        selected={state.category}
        selectedSubcategory={state.subcategory}
        onSelect={(category, subcategory) =>
          patch({
            category,
            subcategory,
            tags: subcategory ? [...new Set([...state.tags, ...subcategory.standard_tags])] : state.tags,
          })
        }
      />
      <MapPickerSheet
        open={mapOpen}
        address={state.address}
        value={state.geo}
        onClose={() => setMapOpen(false)}
        onConfirm={(address, geo) => {
          patch({ address: address || state.address, geo });
          setMapOpen(false);
        }}
      />
    </AdminModal>
  );
}
