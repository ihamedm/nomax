import { toFa } from "@/lib/digits";
import { formatJalali } from "@/lib/jalali";
import type { MarketStatus } from "./types";

const ROLE_EMOJI: Record<string, string> = {
  customer: "👤",
  owner: "🏪",
  admin: "🛡️",
  superadmin: "👑",
};

const STATUS_META: Record<
  MarketStatus,
  { label: string; tone: string; className: string }
> = {
  empty: { label: "بدون داده", tone: "slate", className: "bg-slate-100 text-slate-500" },
  no_supply: { label: "بدون عرضه", tone: "rose", className: "bg-rose-50 text-rose-700" },
  no_demand: { label: "بدون تقاضا", tone: "slate", className: "bg-slate-100 text-slate-600" },
  urgent: { label: "جذب فوری", tone: "amber", className: "bg-amber-50 text-amber-700" },
  shortage: { label: "کمبود عرضه", tone: "rose", className: "bg-rose-50 text-rose-700" },
  surplus: { label: "عرضه مازاد", tone: "sky", className: "bg-sky-50 text-sky-700" },
  balanced: { label: "متعادل", tone: "brand", className: "bg-brand-50 text-brand-700" },
};

export function roleEmoji(role: string): string {
  return ROLE_EMOJI[role] ?? "👤";
}

export function marketStatusMeta(status: MarketStatus) {
  return STATUS_META[status] ?? STATUS_META.empty;
}

export function formatDuration(seconds: number | null | undefined): string {
  if (seconds === null || seconds === undefined) return "—";
  if (seconds < 60) return `${toFa(Math.round(seconds))} ثانیه`;
  if (seconds < 3600) return `${toFa(Math.round(seconds / 60))} دقیقه`;
  const shortDecimal = (value: number) =>
    value >= 10 ? String(Math.round(value)) : String(Number(value.toFixed(1))).replace(".", "٫");
  if (seconds < 86400) {
    return `${toFa(shortDecimal(seconds / 3600))} ساعت`;
  }
  return `${toFa(shortDecimal(seconds / 86400))} روز`;
}

export function formatNumber(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return new Intl.NumberFormat("fa-IR").format(value);
}

export function shortDateLabel(isoDate: string): string {
  return formatJalali(`${isoDate}T12:00:00+03:30`, {
    month: "short",
    day: "numeric",
  });
}

export function shortHourLabel(hour: number): string {
  return `${toFa(hour)}`;
}

export const FUNNEL_LABELS: Record<string, string> = {
  today: "امروز",
  week: "این هفته",
  month: "این ماه",
  all: "کل زمان",
};

export const QUOTE_STATUS_LABELS: Record<string, string> = {
  active: "فعال",
  accepted: "پذیرفته‌شده",
  cancelled: "لغوشده",
  expired: "منقضی",
};

export const QUOTE_STATUS_COLORS: Record<string, string> = {
  active: "#10a56f",
  accepted: "#0284c7",
  cancelled: "#e11d48",
  expired: "#d97706",
};

export const TIMING_LABELS: Record<string, string> = {
  sent: "ثبت تا ارسال به کسب‌وکار",
  seen: "ثبت تا مشاهده مالک",
  offer: "ثبت تا اولین پیشنهاد",
  choice: "ثبت تا انتخاب مشتری",
};
