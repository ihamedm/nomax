const FA_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];

export function fa(value: string | number): string {
  return String(value).replace(/\d/g, (digit) => FA_DIGITS[Number(digit)]);
}

/** 9123456789 -> 0912 345 6789 */
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
