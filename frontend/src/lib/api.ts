import { tokens } from "@/lib/tokens";

const BASE = `${import.meta.env.VITE_API_BASE_URL ?? ""}/api/v1`;

export class ApiError extends Error {
  code: string;
  status: number;
  details?: unknown;

  constructor(code: string, message: string, status: number, details?: unknown) {
    super(message);
    this.name = "ApiError";
    this.code = code;
    this.status = status;
    this.details = details;
  }
}

interface ErrorBody {
  error?: { code?: string; message?: string; details?: unknown };
}

function expireSession(): void {
  tokens.clear();
  window.dispatchEvent(new Event("nomax:session-expired"));
}

async function doRefresh(): Promise<boolean> {
  if (!tokens.refresh) return false;
  try {
    const response = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: tokens.refresh }),
    });
    if (!response.ok) {
      expireSession();
      return false;
    }
    const body = (await response.json()) as { data?: { access: string; refresh: string } };
    if (!body.data) {
      expireSession();
      return false;
    }
    tokens.set(body.data.access, body.data.refresh);
    return true;
  } catch {
    // Network failure while refreshing: keep the refresh token so a retry can
    // still succeed when connectivity returns.
    return false;
  }
}

let refreshing: Promise<boolean> | null = null;

/** Single-flight refresh: concurrent 401s must not rotate the same token twice. */
function refreshTokens(): Promise<boolean> {
  if (!refreshing) {
    refreshing = doRefresh().finally(() => {
      refreshing = null;
    });
  }
  return refreshing;
}

async function request<T, M>(
  path: string,
  init: RequestInit,
  retry: boolean,
): Promise<{ data: T; meta: M | undefined }> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type") && !(init.body instanceof FormData)) {
    headers.set("Content-Type", "application/json");
  }
  if (tokens.access) headers.set("Authorization", `Bearer ${tokens.access}`);

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("network_error", "network_error", 0);
  }

  if (response.status === 401 && retry && tokens.refresh) {
    if (await refreshTokens()) return request<T, M>(path, init, false);
  }

  const body = (await response.json().catch(() => null)) as
    | ({ data?: T; meta?: M } & ErrorBody)
    | null;
  if (!response.ok || !body || body.data === undefined) {
    const error = body?.error;
    throw new ApiError(
      error?.code ?? "http_error",
      error?.message ?? `http_${response.status}`,
      response.status,
      error?.details,
    );
  }
  return { data: body.data, meta: body.meta };
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const { data } = await request<T, never>(path, init, retry);
  return data;
}

/** Like `api`, but keeps the envelope `meta` (used by cursor-paginated lists). */
export async function apiWithMeta<T, M>(
  path: string,
  init: RequestInit = {},
  retry = true,
): Promise<{ data: T; meta: M | undefined }> {
  return request<T, M>(path, init, retry);
}

const MESSAGES: Record<string, string> = {
  network_error: "ارتباط با سرور برقرار نشد. اتصال خود را بررسی کنید.",
  otp_invalid: "کد وارد شده نامعتبر یا منقضی شده است.",
  otp_rate_limited: "تعداد درخواست‌ها زیاد است. کمی بعد دوباره تلاش کنید.",
  validation_error: "اطلاعات وارد شده معتبر نیست.",
  forbidden: "شما دسترسی لازم برای این کار را ندارید.",
  auth_unauthorized: "لطفاً دوباره وارد شوید.",
  token_revoked: "نشست شما منقضی شده است. دوباره وارد شوید.",
  account_disabled: "این حساب غیرفعال شده است.",
  not_found: "موردی پیدا نشد.",
  conflict: "این اطلاعات قبلاً ثبت شده است.",
  sms_provider_unavailable: "ارسال پیامک در حال حاضر ممکن نیست. کمی بعد تلاش کنید.",
  not_ready: "سرویس موقتاً آماده نیست.",
  storage_not_configured: "اتصال ArvanCloud S3 هنوز تنظیم نشده است.",
  storage_error: "عملیات روی فضای ابری آروان انجام نشد.",
  geocoder_unavailable: "جستجوی آدرس در حال حاضر ممکن نیست. کمی بعد دوباره تلاش کنید.",
  geocoder_not_found: "آدرسی برای این موقعیت پیدا نشد.",
  geocoder_invalid_response: "پاسخ سرویس آدرس نامعتبر بود.",
  invalid_phone_business: "شماره تماس فروشگاه معتبر نیست.",
  invalid_coordinates: "موقعیت انتخاب‌شده معتبر نیست.",
  subcategory_category_mismatch: "زیردسته با دسته‌بندی انتخاب‌شده هم‌خوان نیست.",
  business_limit_reached: "شما به سقف مجاز ثبت کسب‌وکار رسیده‌اید.",
  rejection_reason_required: "دلیل رد کسب‌وکار را وارد کنید.",
  user_id_required: "شناسه کاربر گیرنده را وارد کنید.",
  review_already_exists: "شما قبلاً برای این کسب‌وکار نظر ثبت کرده‌اید.",
  cannot_review_own_business: "شما نمی‌توانید برای کسب‌وکار خود نظر ثبت کنید.",
  review_too_long: "متن نظر حداکثر ۳۰۰ نویسه است.",
  active_quote_exists: "شما یک درخواست فعال دارید و تا بسته شدن آن امکان ثبت درخواست جدید نیست.",
  offer_already_submitted: "برای این درخواست قبلاً پیشنهاد ثبت کرده‌اید.",
  offer_not_pending: "این پیشنهاد دیگر قابل انتخاب نیست.",
  quote_not_active: "این درخواست دیگر فعال نیست.",
  quote_not_cancellable: "این درخواست در وضعیت فعلی قابل لغو نیست.",
  quote_expired: "مهلت این درخواست تمام شده است.",
  invalid_price: "مبلغ پیشنهادی معتبر نیست.",
  title_too_short: "شرح درخواست باید حداقل ۳ نویسه باشد.",
  address_too_short: "آدرس درخواست را کامل‌تر وارد کنید.",
  business_category_mismatch: "کسب‌وکار انتخابی با دسته‌بندی این درخواست هم‌خوان نیست.",
  too_many_images: "تعداد تصاویر از حد مجاز بیشتر است.",
  backup_unavailable: "پشتیبان‌گیری از پایگاه داده در این محیط در دسترس نیست.",
  backup_s3_not_configured: "اتصال S3 آروان برای آرشیو نسخه‌های پشتیبان تنظیم نشده است.",
  backup_failed: "ساخت نسخه پشتیبان انجام نشد.",
  backup_not_found: "نسخه پشتیبان پیدا نشد.",
  backup_timeout: "عملیات پشتیبان‌گیری بیش از حد طول کشید.",
  backup_too_large: "فایل پشتیبان از حد مجاز بزرگ‌تر است.",
  invalid_backup_file: "فایل انتخاب‌شده یک نسخه پشتیبان معتبر نیست.",
  restore_confirmation_required: "برای بازیابی، عبارت RESTORE را دقیقاً وارد کنید.",
  restore_failed: "بازیابی پایگاه داده انجام نشد؛ پایگاه داده بدون تغییر باقی ماند.",
  image_url_too_long: "نشانی تصویر بیش از حد طولانی است.",
  images_must_be_a_list: "فهرست تصاویر معتبر نیست.",
  invalid_image: "یکی از تصاویر معتبر نیست.",
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return MESSAGES[error.code] ?? error.message;
  return "خطای غیرمنتظره‌ای رخ داد.";
}
