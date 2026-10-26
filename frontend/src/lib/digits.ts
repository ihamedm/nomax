const FA_DIGITS = ["۰", "۱", "۲", "۳", "۴", "۵", "۶", "۷", "۸", "۹"];
const AR_DIGITS = ["٠", "١", "٢", "٣", "٤", "٥", "٦", "٧", "٨", "٩"];

/** Convert every ASCII digit in a value to a Persian digit. */
export function toFa(value: string | number): string {
  return String(value).replace(/\d/g, (digit) => FA_DIGITS[Number(digit)]);
}

/** Convert Persian and Arabic-Indic digits back to ASCII digits. */
export function toEn(value: string): string {
  return value
    .replace(/[۰-۹]/g, (digit) => String(FA_DIGITS.indexOf(digit)))
    .replace(/[٠-٩]/g, (digit) => String(AR_DIGITS.indexOf(digit)));
}

/** Normalize user input (Persian/Arabic digits, spaces, dashes) to ASCII digits. */
export function normalizeDigits(value: string): string {
  return toEn(value).replace(/[\s-]/g, "");
}

export function isNumericInput(value: string): boolean {
  return /^[0-9۰-۹٠-٩]+$/.test(value);
}
