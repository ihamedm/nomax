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

async function refreshTokens(): Promise<boolean> {
  if (!tokens.refresh) return false;
  try {
    const response = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh: tokens.refresh }),
    });
    if (!response.ok) return false;
    const body = (await response.json()) as { data?: { access: string; refresh: string } };
    if (!body.data) return false;
    tokens.set(body.data.access, body.data.refresh);
    return true;
  } catch {
    return false;
  }
}

export async function api<T>(path: string, init: RequestInit = {}, retry = true): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !headers.has("Content-Type")) headers.set("Content-Type", "application/json");
  if (tokens.access) headers.set("Authorization", `Bearer ${tokens.access}`);

  let response: Response;
  try {
    response = await fetch(`${BASE}${path}`, { ...init, headers });
  } catch {
    throw new ApiError("network_error", "network_error", 0);
  }

  if (response.status === 401 && retry && tokens.refresh) {
    if (await refreshTokens()) return api<T>(path, init, false);
  }

  const body = (await response.json().catch(() => null)) as ({ data?: T } & ErrorBody) | null;
  if (!response.ok || !body || body.data === undefined) {
    const error = body?.error;
    throw new ApiError(
      error?.code ?? "http_error",
      error?.message ?? `http_${response.status}`,
      response.status,
      error?.details,
    );
  }
  return body.data;
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
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return MESSAGES[error.code] ?? error.message;
  return "خطای غیرمنتظره‌ای رخ داد.";
}
