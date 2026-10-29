import type { Category, Coordinates, Subcategory } from "@/types";

/** Shared state for the five-step "add business" wizard. */
export interface WizardData {
  title: string;
  description: string;
  category: Category | null;
  subcategory: Subcategory | null;
  address: string;
  is24h: boolean;
  geo: Coordinates | null;
  pictureUrl: string;
  intro: string;
  shopPhone: string;
  instagram: string;
  licenseEnabled: boolean;
  standardTags: string[];
  customTags: string[];
}

export const STEP_LABELS = [
  "کسب‌وکار",
  "راه ارتباطی و آدرس",
  "اطلاعات تکمیلی",
  "خدمات",
  "پیش‌نمایش نهایی",
] as const;

export const TOTAL_STEPS = STEP_LABELS.length;

export const MAX_INTRO = 120;
export const MAX_CUSTOM_TAGS = 4;
export const MAX_TAG_LENGTH = 30;

export const BEHBAHAN_CENTER: Coordinates = { lat: 30.5959, lng: 50.2417 };

export const IRAN_PHONE = /^0\d{10}$/;

export function categoryPath(
  category: Category | null,
  subcategory: Subcategory | null,
): string {
  if (!category) return "";
  return subcategory ? `${category.name} > ${subcategory.name}` : category.name;
}

/** Returns a Persian error message for the step, or null when it can advance. */
export function validateStep(step: number, data: WizardData, acceptedRules: boolean): string | null {
  if (step === 0) {
    if (data.title.trim().length < 3) return "نام کسب‌وکار را وارد کنید (حداقل ۳ حرف).";
    if (data.description.trim().length < 10) return "توضیح کوتاهی درباره کسب‌وکار بنویسید.";
    if (!data.category) return "دسته‌بندی کسب‌وکار را انتخاب کنید.";
  }
  if (step === 1 && data.address.trim().length < 5) {
    return "آدرس کسب‌وکار را وارد کنید.";
  }
  if (step === 2) {
    if (data.intro.length > MAX_INTRO) return `معرفی کوتاه حداکثر ${MAX_INTRO} نویسه است.`;
    if (data.shopPhone.trim() && !IRAN_PHONE.test(data.shopPhone.trim())) {
      return "شماره تماس فروشگاه باید ۱۱ رقم و با ۰ شروع شود.";
    }
  }
  if (step === 4 && !acceptedRules) {
    return "برای ثبت، پذیرش قوانین نومکس الزامی است.";
  }
  return null;
}
