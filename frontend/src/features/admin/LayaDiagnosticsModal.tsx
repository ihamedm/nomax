import { useState, type FormEvent } from "react";
import { useMutation } from "@tanstack/react-query";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fa } from "@/lib/format";
import { AdminModal } from "@/features/admin/AdminModal";
import type { CategorySuggestion } from "@/types";

type Verdict =
  | "working"
  | "rules_only"
  | "no_match"
  | "unavailable"
  | "disabled"
  | "degraded"
  | "unknown";

type LogLevel = "debug" | "info" | "success" | "warning" | "error";
type Severity = "critical" | "warning" | "info";

interface DiagnosticEvent {
  stage: string;
  level: LogLevel;
  message: string;
  duration_ms?: number;
  data?: Record<string, unknown>;
}

interface TuningHint {
  severity: Severity;
  title: string;
  detail: string;
}

interface Health {
  status: "ok" | "error" | "unreachable" | "skipped";
  latency_ms: number;
  http_status: number | null;
  detail: unknown;
  error: string | null;
}

interface Probe {
  status: "ok" | "partial" | "unavailable";
  category?: {
    id: number;
    name: string;
    slug: string;
    icon: string;
  };
  category_confidence?: number;
  subcategory?: {
    id: number;
    name: string;
    slug: string;
    icon: string;
  } | null;
  subcategory_confidence?: number | null;
  error?: string;
}

interface DiagnosticConfig {
  enabled: boolean;
  rules_enabled: boolean;
  base_url: string;
  model: string;
  timeout_seconds: number;
  api_key_configured: boolean;
  max_suggestions: number;
  thresholds: {
    min_category_confidence: number;
    min_category_margin: number;
    min_subcategory_confidence: number;
    high_confidence: number;
    medium_confidence: number;
  };
}

interface DiagnosticResult {
  status: "ok" | "disabled" | "unavailable" | "no_match";
  verdict: Verdict;
  verdict_message: string;
  enabled: boolean;
  model: string;
  elapsed_ms: number;
  pipeline_elapsed_ms: number;
  config: DiagnosticConfig;
  health: Health;
  taxonomy: {
    categories?: number;
    choice_categories?: number;
    subcategories?: number;
  };
  state: { text: string; chars: number };
  suggestions: CategorySuggestion[];
  events: DiagnosticEvent[];
  probe: Probe | null;
  tuning: TuningHint[];
}

const VERDICT_STYLES: Record<Verdict, { box: string; badge: string; label: string }> = {
  working: {
    box: "border-emerald-200 bg-emerald-50 text-emerald-900",
    badge: "bg-emerald-600 text-white",
    label: "Laya کار می‌کند",
  },
  rules_only: {
    box: "border-sky-200 bg-sky-50 text-sky-900",
    badge: "bg-sky-600 text-white",
    label: "فقط لایه قواعد",
  },
  no_match: {
    box: "border-amber-200 bg-amber-50 text-amber-900",
    badge: "bg-amber-500 text-white",
    label: "مدل مطمئن نبود",
  },
  unavailable: {
    box: "border-rose-200 bg-rose-50 text-rose-900",
    badge: "bg-rose-600 text-white",
    label: "Laya در دسترس نیست",
  },
  disabled: {
    box: "border-slate-200 bg-slate-50 text-slate-800",
    badge: "bg-slate-600 text-white",
    label: "Laya غیرفعال است",
  },
  degraded: {
    box: "border-orange-200 bg-orange-50 text-orange-900",
    badge: "bg-orange-500 text-white",
    label: "حالت محدود",
  },
  unknown: {
    box: "border-slate-200 bg-slate-50 text-slate-800",
    badge: "bg-slate-600 text-white",
    label: "نامشخص",
  },
};

const LEVEL_DOT: Record<LogLevel, string> = {
  debug: "bg-slate-300",
  info: "bg-sky-500",
  success: "bg-emerald-500",
  warning: "bg-amber-500",
  error: "bg-rose-500",
};

const LEVEL_ROW: Record<LogLevel, string> = {
  debug: "bg-white",
  info: "bg-white",
  success: "bg-emerald-50/30",
  warning: "bg-amber-50/40",
  error: "bg-rose-50/40",
};

const SEVERITY_STYLES: Record<Severity, { box: string; badge: string; label: string }> = {
  critical: {
    box: "border-rose-200 bg-rose-50/70",
    badge: "bg-rose-600 text-white",
    label: "مهم",
  },
  warning: {
    box: "border-amber-200 bg-amber-50/70",
    badge: "bg-amber-500 text-white",
    label: "هشدار",
  },
  info: {
    box: "border-sky-200 bg-sky-50/70",
    badge: "bg-sky-600 text-white",
    label: "پیشنهاد",
  },
};

const STAGE_LABELS: Record<string, string> = {
  config: "تنظیمات",
  health: "سلامت سرویس",
  state: "نرمال‌سازی متن",
  taxonomy: "واژگان دسته‌ها",
  rules_category: "قواعد دسته",
  rules_subcategory: "قواعد زیردسته",
  laya_category: "Laya / دسته",
  laya_subcategory: "Laya / زیردسته",
  laya_probe: "بررسی مستقیم",
  laya_probe_category: "بررسی مستقیم / دسته",
  laya_probe_subcategory: "بررسی مستقیم / زیردسته",
  category_decision: "تصمیم دسته",
  subcategory_decision: "تصمیم زیردسته",
  result: "نتیجه نهایی",
};

const EXAMPLES = [
  {
    label: "رستوران",
    title: "رستوران سنتی بهار",
    description: "غذای ایرانی، کباب و دیزی؛ در بهبهان واقع شده است.",
  },
  {
    label: "دندانپزشکی",
    title: "دندانپزشکی لبخند",
    description: "ایمپلنت، ترمیم و جرم‌گیری دندان",
  },
  {
    label: "قطعات خودرو",
    title: "فروشگاه قطعات خودرو بهبهان",
    description: "لوازم یدکی، باتری و لاستیک خودرو",
  },
  {
    label: "مبهم",
    title: "امداد نومکس",
    description: "پشتیبانی و رسیدگی به درخواست‌های ویژه",
  },
];

function percent(value: number | null | undefined): string {
  if (value === null || value === undefined) return "—";
  return `${fa((value * 100).toFixed(1).replace(".", "٫"))}٪`;
}

function stageLabel(stage: string): string {
  return STAGE_LABELS[stage] ?? stage;
}

function prettyData(data: unknown): string {
  try {
    return JSON.stringify(data, null, 2);
  } catch {
    return String(data);
  }
}

function SuggestionCard({ suggestion }: { suggestion: CategorySuggestion }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <p className="text-sm font-black text-slate-900">
            <span className="ml-1">{suggestion.category.icon}</span>
            {suggestion.category.name}
            {suggestion.subcategory ? (
              <span className="font-bold text-slate-500"> › {suggestion.subcategory.name}</span>
            ) : null}
          </p>
          <p className="mt-1 text-[10px] text-slate-400">
            دسته از {suggestion.category_source === "rules" ? "قواعد" : "Laya"}
            {suggestion.subcategory_source
              ? ` · زیردسته از ${suggestion.subcategory_source === "rules" ? "قواعد" : "Laya"}`
              : ""}
          </p>
        </div>
        <div className="flex items-center gap-1.5">
          <span
            className={cn(
              "rounded-full px-2 py-0.5 text-[10px] font-bold",
              suggestion.quality === "high"
                ? "bg-emerald-100 text-emerald-700"
                : suggestion.quality === "medium"
                  ? "bg-amber-100 text-amber-700"
                  : "bg-slate-100 text-slate-600",
            )}
          >
            {suggestion.quality === "high"
              ? "اطمینان بالا"
              : suggestion.quality === "medium"
                ? "اطمینان متوسط"
                : "اطمینان کم"}
          </span>
          <span className="text-xs font-black text-slate-700" dir="ltr">
            {percent(suggestion.confidence)}
          </span>
        </div>
      </div>
      <div className="mt-2 flex flex-wrap gap-3 text-[10px] text-slate-500">
        <span>دسته: {percent(suggestion.category_confidence)}</span>
        {suggestion.subcategory_confidence !== null && (
          <span>زیردسته: {percent(suggestion.subcategory_confidence)}</span>
        )}
      </div>
    </div>
  );
}

export function LayaDiagnosticsModal({ onClose }: { onClose: () => void }) {
  const [title, setTitle] = useState("رستوران سنتی بهار");
  const [description, setDescription] = useState(
    "غذای ایرانی، کباب و دیزی؛ در بهبهان واقع شده است.",
  );
  const [rulesEnabled, setRulesEnabled] = useState(true);
  const [probeLaya, setProbeLaya] = useState(true);

  const run = useMutation({
    mutationFn: () =>
      api<DiagnosticResult>("/admin/categories/suggest/diagnose", {
        method: "POST",
        body: JSON.stringify({
          title: title.trim(),
          description: description.trim() || null,
          rules_enabled: rulesEnabled,
          probe_laya: probeLaya,
        }),
      }),
  });

  const result = run.data;

  function submit(event: FormEvent) {
    event.preventDefault();
    if (title.trim().length < 3 || run.isPending) return;
    run.mutate();
  }

  return (
    <AdminModal title="تست Laya و تنظیم دقیق پیشنهاد دسته" onClose={onClose} className="max-w-6xl">
      <div className="space-y-4">
        <div className="rounded-xl border border-brand-100 bg-brand-50/60 px-3.5 py-3 text-[11px] leading-6 text-brand-800">
          این ابزار فقط برای مدیران است و هیچ داده‌ای را ذخیره یا تغییر نمی‌دهد. یک متن نمونه وارد
          کنید تا ببینید لایه قواعد، خود مدل Laya، آستانه‌ها و زمان پاسخ چه رفتاری دارند.
        </div>

        <form onSubmit={submit} className="space-y-3 rounded-2xl border border-slate-200 bg-white p-3.5">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="space-y-1 text-xs text-slate-500">
              عنوان کسب‌وکار
              <Input
                required
                minLength={3}
                maxLength={160}
                value={title}
                onChange={(event) => setTitle(event.target.value)}
                placeholder="مثلاً رستوران سنتی بهار"
              />
            </label>
            <div className="flex flex-wrap items-end gap-1.5 text-[10px] text-slate-400">
              <span className="mb-2 block w-full">نمونه‌های آماده:</span>
              {EXAMPLES.map((example) => (
                <button
                  key={example.label}
                  type="button"
                  onClick={() => {
                    setTitle(example.title);
                    setDescription(example.description);
                    run.reset();
                  }}
                  className="rounded-full border border-slate-200 bg-slate-50 px-2.5 py-1 text-[10px] text-slate-600 transition-colors hover:border-brand-300 hover:text-brand-700"
                >
                  {example.label}
                </button>
              ))}
            </div>
          </div>

          <label className="block space-y-1 text-xs text-slate-500">
            توضیحات
            <textarea
              maxLength={2000}
              value={description}
              onChange={(event) => setDescription(event.target.value)}
              placeholder="خدمات، محصولات یا ویژگی‌های کسب‌وکار…"
              className="min-h-20 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </label>

          <div className="flex flex-wrap items-center gap-x-5 gap-y-2 text-xs text-slate-700">
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={rulesEnabled}
                onChange={(event) => setRulesEnabled(event.target.checked)}
              />
              استفاده از لایه قواعد فارسی
            </label>
            <label className="flex items-center gap-2">
              <input
                type="checkbox"
                checked={probeLaya}
                onChange={(event) => setProbeLaya(event.target.checked)}
              />
              بررسی مستقیم Laya (مستقل از قواعد)
            </label>
            <span className="text-[10px] text-slate-400">
              برای مقایسه، یک بار با قواعد و یک بار بدون قواعد اجرا کنید.
            </span>
          </div>

          <div className="flex flex-wrap items-center gap-2">
            <Button type="submit" loading={run.isPending} disabled={title.trim().length < 3}>
              اجرای تست
            </Button>
            {run.isPending && (
              <span className="text-[11px] text-slate-400">
                ممکن است چند ثانیه طول بکشد؛ Laya روی CPU اجرا می‌شود.
              </span>
            )}
          </div>
        </form>

        {run.error && (
          <p className="rounded-xl border border-rose-200 bg-rose-50 px-3 py-2 text-xs text-rose-700">
            {errorMessage(run.error)}
          </p>
        )}

        {result && (
          <div className="space-y-4">
            <div className={cn("rounded-2xl border p-3.5", VERDICT_STYLES[result.verdict].box)}>
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div>
                  <span
                    className={cn(
                      "inline-flex rounded-full px-2.5 py-1 text-[10px] font-black",
                      VERDICT_STYLES[result.verdict].badge,
                    )}
                  >
                    {VERDICT_STYLES[result.verdict].label}
                  </span>
                  <p className="mt-2 text-xs leading-6">{result.verdict_message}</p>
                </div>
                <div className="flex flex-wrap gap-1.5 text-[10px]">
                  <span className="rounded-full bg-white/70 px-2 py-0.5">
                    کل: {fa(result.elapsed_ms)}ms
                  </span>
                  <span className="rounded-full bg-white/70 px-2 py-0.5">
                    خط لوله: {fa(result.pipeline_elapsed_ms)}ms
                  </span>
                  <span className="rounded-full bg-white/70 px-2 py-0.5" dir="ltr">
                    {result.model}
                  </span>
                </div>
              </div>
            </div>

            <div className="grid gap-2 sm:grid-cols-3">
              <div className="rounded-xl border border-slate-200 bg-white p-3">
                <p className="text-[10px] text-slate-400">health سرویس</p>
                <p className="mt-1 text-sm font-black text-slate-900">
                  {result.health.status === "ok"
                    ? "سالم"
                    : result.health.status === "skipped"
                      ? "بررسی نشد"
                      : result.health.status === "unreachable"
                        ? "در دسترس نیست"
                        : "خطا"}
                </p>
                <p className="mt-0.5 text-[10px] text-slate-400">
                  {result.health.http_status ? `HTTP ${result.health.http_status} · ` : ""}
                  {fa(result.health.latency_ms)}ms
                </p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-3">
                <p className="text-[10px] text-slate-400">واژگان فعال</p>
                <p className="mt-1 text-sm font-black text-slate-900">
                  {fa(result.taxonomy.choice_categories ?? 0)} دسته ·{" "}
                  {fa(result.taxonomy.subcategories ?? 0)} زیردسته
                </p>
                <p className="mt-0.5 text-[10px] text-slate-400">متن نرمال‌شده: {fa(result.state.chars)} نویسه</p>
              </div>
              <div className="rounded-xl border border-slate-200 bg-white p-3">
                <p className="text-[10px] text-slate-400">حالت اجرا</p>
                <p className="mt-1 text-sm font-black text-slate-900">
                  {result.config.rules_enabled ? "ترکیبی (قواعد + Laya)" : "Laya خام"}
                </p>
                <p className="mt-0.5 text-[10px] text-slate-400">
                  {result.config.api_key_configured ? "API key تنظیم شده" : "بدون API key"}
                </p>
              </div>
            </div>

            <section className="rounded-2xl border border-slate-200 bg-white p-3.5">
              <h3 className="text-xs font-black text-slate-900">نتیجه پیشنهاد</h3>
              {result.suggestions.length === 0 ? (
                <p className="mt-2 rounded-xl bg-slate-50 px-3 py-3 text-[11px] text-slate-500">
                  پیشنهادی برگشت داده نشد. علت دقیق را در لاگ‌های پایین ببینید.
                </p>
              ) : (
                <div className="mt-2 space-y-2">
                  {result.suggestions.map((suggestion) => (
                    <SuggestionCard
                      key={`${suggestion.category.id}-${suggestion.subcategory?.id ?? "none"}`}
                      suggestion={suggestion}
                    />
                  ))}
                </div>
              )}
            </section>

            {result.probe && (
              <section className="rounded-2xl border border-slate-200 bg-white p-3.5">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <h3 className="text-xs font-black text-slate-900">نظر مستقیم Laya</h3>
                  <span
                    className={cn(
                      "rounded-full px-2 py-0.5 text-[10px] font-bold",
                      result.probe.status === "ok"
                        ? "bg-emerald-100 text-emerald-700"
                        : result.probe.status === "partial"
                          ? "bg-amber-100 text-amber-700"
                          : "bg-rose-100 text-rose-700",
                    )}
                  >
                    {result.probe.status === "ok"
                      ? "پاسخ کامل"
                      : result.probe.status === "partial"
                        ? "پاسخ ناقص"
                        : "بدون پاسخ"}
                  </span>
                </div>
                {result.probe.status === "unavailable" ? (
                  <p className="mt-2 text-[11px] text-rose-600">
                    {result.probe.error ?? "Laya پاسخ نداد."}
                  </p>
                ) : (
                  <div className="mt-2 grid gap-2 sm:grid-cols-2">
                    <div className="rounded-xl bg-slate-50 px-3 py-2">
                      <p className="text-[10px] text-slate-400">دسته</p>
                      <p className="mt-0.5 text-sm font-bold text-slate-900">
                        {result.probe.category?.icon} {result.probe.category?.name ?? "—"}
                      </p>
                      <p className="mt-0.5 text-[10px] text-slate-500">
                        اطمینان: {percent(result.probe.category_confidence)}
                      </p>
                    </div>
                    <div className="rounded-xl bg-slate-50 px-3 py-2">
                      <p className="text-[10px] text-slate-400">زیردسته</p>
                      <p className="mt-0.5 text-sm font-bold text-slate-900">
                        {result.probe.subcategory
                          ? `${result.probe.subcategory.icon} ${result.probe.subcategory.name}`
                          : "—"}
                      </p>
                      <p className="mt-0.5 text-[10px] text-slate-500">
                        اطمینان: {percent(result.probe.subcategory_confidence)}
                      </p>
                    </div>
                  </div>
                )}
              </section>
            )}

            {result.tuning.length > 0 && (
              <section className="space-y-2">
                <h3 className="text-xs font-black text-slate-900">چطور نتیجه بهتر شود؟</h3>
                {result.tuning.map((hint) => (
                  <div
                    key={`${hint.severity}-${hint.title}`}
                    className={cn("rounded-xl border px-3 py-2.5", SEVERITY_STYLES[hint.severity].box)}
                  >
                    <div className="flex flex-wrap items-center gap-2">
                      <span
                        className={cn(
                          "rounded-full px-2 py-0.5 text-[9px] font-black",
                          SEVERITY_STYLES[hint.severity].badge,
                        )}
                      >
                        {SEVERITY_STYLES[hint.severity].label}
                      </span>
                      <p className="text-[11px] font-black text-slate-800">{hint.title}</p>
                    </div>
                    <p className="mt-1 text-[10px] leading-5 text-slate-600">{hint.detail}</p>
                  </div>
                ))}
              </section>
            )}

            <section className="rounded-2xl border border-slate-200 bg-white">
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-100 px-3.5 py-2.5">
                <h3 className="text-xs font-black text-slate-900">لاگ مرحله‌به‌مرحله</h3>
                <span className="text-[10px] text-slate-400">
                  {fa(result.events.length)} رویداد · جدیدترین‌ها در پایین
                </span>
              </div>
              <div className="max-h-[28rem] overflow-y-auto">
                {result.events.map((event, index) => (
                  <div
                    key={`${event.stage}-${index}`}
                    className={cn(
                      "flex gap-2.5 border-b border-slate-100 px-3.5 py-2.5 last:border-0",
                      LEVEL_ROW[event.level],
                    )}
                  >
                    <span
                      className={cn("mt-1.5 h-2 w-2 shrink-0 rounded-full", LEVEL_DOT[event.level])}
                      aria-hidden
                    />
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="rounded-md bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold text-slate-600">
                          {stageLabel(event.stage)}
                        </span>
                        {event.duration_ms !== undefined && (
                          <span className="text-[9px] text-slate-400" dir="ltr">
                            {event.duration_ms}ms
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-[11px] leading-5 text-slate-700">{event.message}</p>
                      {event.data && (
                        <details className="mt-1">
                          <summary className="cursor-pointer text-[9px] text-slate-400 hover:text-slate-600">
                            داده خام
                          </summary>
                          <pre
                            dir="ltr"
                            className="mt-1 max-h-64 overflow-auto rounded-lg bg-slate-900 p-2 text-left text-[9px] leading-4 text-slate-100"
                          >
                            {prettyData(event.data)}
                          </pre>
                        </details>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </section>

            <details className="rounded-2xl border border-slate-200 bg-white px-3.5 py-2.5">
              <summary className="cursor-pointer text-xs font-black text-slate-900">
                تنظیمات فعلی و متن نرمال‌شده
              </summary>
              <div className="mt-3 grid gap-2 text-[10px] sm:grid-cols-2 lg:grid-cols-3">
                {[
                  ["LAYA_ENABLED", result.config.enabled ? "true" : "false"],
                  ["LAYA_RULES_ENABLED", result.config.rules_enabled ? "true" : "false"],
                  ["مدل", result.config.model],
                  ["آدرس سرویس", result.config.base_url],
                  ["timeout", `${result.config.timeout_seconds}s`],
                  ["حداکثر پیشنهاد", String(result.config.max_suggestions)],
                  [
                    "حداقل اطمینان دسته",
                    percent(result.config.thresholds.min_category_confidence),
                  ],
                  ["حداقل margin دسته", percent(result.config.thresholds.min_category_margin)],
                  [
                    "حداقل اطمینان زیردسته",
                    percent(result.config.thresholds.min_subcategory_confidence),
                  ],
                  ["آستانه high", percent(result.config.thresholds.high_confidence)],
                  ["آستانه medium", percent(result.config.thresholds.medium_confidence)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded-lg bg-slate-50 px-2.5 py-2">
                    <p className="text-slate-400">{label}</p>
                    <p className="mt-0.5 break-words font-bold text-slate-700" dir="ltr">
                      {value}
                    </p>
                  </div>
                ))}
              </div>
              <div className="mt-3">
                <p className="text-[10px] text-slate-400">متن نرمال‌شده‌ای که مدل می‌بیند:</p>
                <pre className="mt-1 whitespace-pre-wrap rounded-lg bg-slate-50 p-2.5 text-[10px] leading-5 text-slate-600">
                  {result.state.text || "—"}
                </pre>
              </div>
            </details>
          </div>
        )}
      </div>
    </AdminModal>
  );
}
