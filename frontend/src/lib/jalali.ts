const TEHRAN_TIME_ZONE = "Asia/Tehran";

function asDate(value: Date | string | number): Date | null {
  const date = value instanceof Date ? value : new Date(value);
  return Number.isNaN(date.getTime()) ? null : date;
}

/** Format a date with the Persian (Jalali) calendar in Tehran time. */
export function formatJalali(
  value: Date | string | number,
  options: Intl.DateTimeFormatOptions = {},
): string {
  const date = asDate(value);
  if (!date) return "";
  const hasExplicitParts = [
    "dateStyle",
    "timeStyle",
    "year",
    "month",
    "day",
    "weekday",
    "hour",
    "minute",
    "second",
  ].some((key) => key in options);
  return new Intl.DateTimeFormat("fa-IR-u-ca-persian", {
    timeZone: TEHRAN_TIME_ZONE,
    ...(hasExplicitParts ? {} : { dateStyle: "medium" }),
    ...options,
  }).format(date);
}

export function formatJalaliDateTime(value: Date | string | number): string {
  return formatJalali(value, { dateStyle: "medium", timeStyle: "short" });
}

/** Short relative time for lists, e.g. «۳ دقیقه پیش». */
export function formatRelative(value: Date | string | number): string {
  const date = asDate(value);
  if (!date) return "";
  const seconds = Math.round((date.getTime() - Date.now()) / 1000);
  const formatter = new Intl.RelativeTimeFormat("fa", { numeric: "auto" });
  const units: Array<[Intl.RelativeTimeFormatUnit, number]> = [
    ["year", 60 * 60 * 24 * 365],
    ["month", 60 * 60 * 24 * 30],
    ["day", 60 * 60 * 24],
    ["hour", 60 * 60],
    ["minute", 60],
    ["second", 1],
  ];
  for (const [unit, unitSeconds] of units) {
    if (Math.abs(seconds) >= unitSeconds || unit === "second") {
      return formatter.format(Math.round(seconds / unitSeconds), unit);
    }
  }
  return "";
}
