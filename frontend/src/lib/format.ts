import { toFa } from "@/lib/digits";

export const fa = toFa;

/** 9123456789 -> ۰۹۱۲ ۳۴۵ ۶۷۸۹ */
export function formatPhone(phone: string): string {
  const ten = phone.length === 11 && phone.startsWith("0") ? phone.slice(1) : phone;
  if (ten.length !== 10) return fa(phone);
  return fa(`0${ten.slice(0, 3)} ${ten.slice(3, 6)} ${ten.slice(6)}`);
}

export const ROLE_LABELS: Record<string, string> = {
  customer: "مشتری",
  owner: "کسب‌وکار",
  admin: "مدیر",
  superadmin: "مدیر کل",
};

/** 250 -> «۲۵۰ متر»، 1250 -> «۱٫۳ کیلومتر» */
export function formatDistance(meters: number | null | undefined): string {
  if (meters === null || meters === undefined) return "";
  if (meters < 1000) {
    const rounded = Math.max(10, Math.round(meters / 10) * 10);
    return `${fa(rounded)} متر`;
  }
  const kilometers = (meters / 1000).toFixed(1).replace(".", "٫");
  return `${fa(kilometers)} کیلومتر`;
}

export function formatRating(rating: number | null | undefined): string {
  if (!rating) return "بدون امتیاز";
  return fa((Math.round(rating * 10) / 10).toFixed(1).replace(".", "٫"));
}

export const GROUP_LABELS: Record<string, string> = {
  business: "کسب‌وکارها",
  review: "نظرات",
  category: "دسته‌بندی‌ها",
  quote: "استعلام‌ها",
  ad: "تبلیغات",
  stats: "آمار",
  notification: "اعلان‌ها",
  user: "کاربران",
  admin: "مدیریت",
};

export const PERMISSION_LABELS: Record<string, string> = {
  "business.read": "مشاهده کسب‌وکارها",
  "business.create": "ایجاد کسب‌وکار",
  "business.update": "ویرایش کسب‌وکار",
  "business.delete": "حذف کسب‌وکار",
  "business.approve": "تأیید کسب‌وکار",
  "business.license.verify": "بررسی پروانه کسب",
  "review.read": "مشاهده نظرات",
  "review.create": "ثبت نظر",
  "review.moderate": "تأیید / رد نظرات",
  "review.reply": "پاسخ به نظرات",
  "category.read": "مشاهده دسته‌بندی‌ها",
  "category.manage": "مدیریت دسته‌بندی‌ها",
  "category.suggestion.manage": "مدیریت پیشنهاد دسته",
  "quote.read": "مشاهده استعلام‌ها",
  "quote.create": "ایجاد استعلام",
  "quote.manage": "مدیریت استعلام‌ها",
  "ad.manage": "مدیریت تبلیغات",
  "stats.read": "مشاهده آمار",
  "notification.manage": "مدیریت اعلان‌ها",
  "user.read": "مشاهده کاربران",
  "user.manage": "مدیریت کاربران",
  "user.role.manage": "تغییر نقش کاربران",
  "admin.settings.manage": "تنظیمات مدیریت",
  "admin.audit.read": "مشاهده گزارش رویدادها",
  "admin.dev": "ابزارهای توسعه",
};

export function permissionLabel(code: string): string {
  return PERMISSION_LABELS[code] ?? code;
}
