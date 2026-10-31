import { useEffect, useState } from "react";

import { toFa } from "@/lib/digits";
import type { OfferStatus, QuoteStatus } from "./types";

export const QUOTE_STATUS_LABELS: Record<QuoteStatus, string> = {
  active: "فعال",
  accepted: "پذیرفته‌شده",
  cancelled: "لغوشده",
  expired: "منقضی",
};

export const QUOTE_STATUS_TONES: Record<
  QuoteStatus,
  "brand" | "sky" | "amber" | "rose" | "slate"
> = {
  active: "brand",
  accepted: "sky",
  cancelled: "rose",
  expired: "amber",
};

export const OFFER_STATUS_LABELS: Record<OfferStatus, string> = {
  pending: "در انتظار پاسخ مشتری",
  accepted: "پذیرفته‌شده",
  expired: "منقضی",
  declined: "ردشده",
};

export const OFFER_STATUS_TONES: Record<
  OfferStatus,
  "brand" | "sky" | "amber" | "rose" | "slate"
> = {
  pending: "amber",
  accepted: "brand",
  expired: "slate",
  declined: "rose",
};

export const OFFER_UNITS = ["کل کار", "متری", "ساعتی", "دستگاهی", "موردی"];

/** 2500000 -> «۲٬۵۰۰٬۰۰۰ تومان» */
export function formatToman(value: number | null | undefined): string {
  if (value === null || value === undefined) return "قیمت نامشخص";
  return `${new Intl.NumberFormat("fa-IR").format(Math.round(value))} تومان`;
}

/** Short countdown used on quote cards and details. */
export function formatCountdown(
  expiresAt: string | null | undefined,
  now: number = Date.now(),
): string {
  if (!expiresAt) return "";
  const target = new Date(expiresAt).getTime();
  if (Number.isNaN(target)) return "";
  const remaining = target - now;
  if (remaining <= 0) return "مهلت تمام شده";

  const minutes = Math.ceil(remaining / 60000);
  const days = Math.floor(minutes / (60 * 24));
  const hours = Math.floor((minutes % (60 * 24)) / 60);
  const mins = minutes % 60;

  if (days > 0) {
    return hours > 0
      ? `${toFa(days)} روز و ${toFa(hours)} ساعت مانده`
      : `${toFa(days)} روز مانده`;
  }
  if (hours > 0) {
    return mins > 0
      ? `${toFa(hours)} ساعت و ${toFa(mins)} دقیقه مانده`
      : `${toFa(hours)} ساعت مانده`;
  }
  if (mins > 0) return `${toFa(mins)} دقیقه مانده`;
  return "کمتر از یک دقیقه مانده";
}

export function useCountdown(expiresAt: string | null | undefined): string {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!expiresAt) return;
    setNow(Date.now());
    const timer = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(timer);
  }, [expiresAt]);
  return formatCountdown(expiresAt, now);
}

export function isActiveQuote(quote: { status: QuoteStatus; expires_at?: string | null }): boolean {
  if (quote.status !== "active") return false;
  if (!quote.expires_at) return true;
  return new Date(quote.expires_at).getTime() > Date.now();
}
