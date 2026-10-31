import { useState } from "react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";
import type { Quote } from "./types";
import { DispatchProgress } from "./DispatchProgress";
import {
  QUOTE_STATUS_LABELS,
  QUOTE_STATUS_TONES,
  formatToman,
  isActiveQuote,
  useCountdown,
} from "./quote-utils";
import { ClipboardIcon, ClockIcon, PinIcon, SparkIcon } from "./icons";

function QuoteStatusBadge({ quote }: { quote: Quote }) {
  return (
    <Badge tone={QUOTE_STATUS_TONES[quote.status] ?? "slate"}>
      {QUOTE_STATUS_LABELS[quote.status] ?? quote.status}
    </Badge>
  );
}

function Countdown({ expiresAt }: { expiresAt?: string | null }) {
  const text = useCountdown(expiresAt);
  if (!text) return null;
  const expired = text === "مهلت تمام شده";
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 rounded-full px-2.5 py-1 text-[10px] font-medium",
        expired ? "bg-slate-100 text-slate-500" : "bg-amber-50 text-amber-700",
      )}
    >
      <ClockIcon className="h-3.5 w-3.5" />
      {text}
    </span>
  );
}

function ActiveQuoteCard({ quote }: { quote: Quote }) {
  const accepted = quote.accepted_offer;
  return (
    <article className="overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-sm">
      <div className="space-y-3 p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              {quote.category && (
                <span className="text-[11px] font-medium text-slate-400">
                  {quote.category.icon} {quote.category.name}
                  {quote.subcategory ? ` › ${quote.subcategory.name}` : ""}
                </span>
              )}
              {quote.is_urgent && <Badge tone="amber">فوری</Badge>}
            </div>
            <h2 className="mt-1 text-base font-black text-slate-900">{quote.title}</h2>
            <p className="mt-1 line-clamp-2 text-xs leading-6 text-slate-500">
              {quote.description || quote.address}
            </p>
          </div>
          <QuoteStatusBadge quote={quote} />
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <Countdown expiresAt={quote.expires_at} />
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] text-slate-600">
            <ClipboardIcon className="h-3.5 w-3.5" />
            {toFa(quote.offers_count)} پیشنهاد
          </span>
          {quote.created_at && (
            <span className="text-[10px] text-slate-400">{formatJalali(quote.created_at)}</span>
          )}
        </div>

        <div className="flex items-start gap-2 rounded-xl bg-slate-50 px-3 py-2 text-[11px] leading-6 text-slate-500">
          <PinIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
          <span className="min-w-0">
            {quote.address}
            {quote.neighborhood ? ` · ${quote.neighborhood}` : ""}
          </span>
        </div>

        <DispatchProgress dispatch={quote.dispatch} />

        {accepted ? (
          <div className="rounded-2xl border border-brand-200 bg-brand-50 p-3">
            <div className="flex items-center justify-between gap-2">
              <p className="text-[11px] font-black text-brand-700">پیشنهاد انتخاب‌شده</p>
              <Badge tone="brand">قطعی</Badge>
            </div>
            <div className="mt-2 flex items-end justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-slate-900">
                  {accepted.business?.name ?? "کسب‌وکار"}
                </p>
                <p className="mt-0.5 text-[10px] text-slate-500" dir="ltr">
                  {accepted.business?.phone_business ?? "شماره در جزئیات"}
                </p>
              </div>
              <p className="shrink-0 text-sm font-black text-brand-700">
                {formatToman(accepted.price)}
              </p>
            </div>
          </div>
        ) : quote.offers_count === 0 ? (
          <div className="flex items-center gap-2 rounded-xl border border-dashed border-slate-200 px-3 py-2.5 text-[11px] text-slate-500">
            <SparkIcon className="h-4 w-4 shrink-0 text-brand-500" />
            در انتظار رسیدن اولین پیشنهاد از کسب‌وکارها…
          </div>
        ) : (
          <div className="flex items-center justify-between gap-2 rounded-xl border border-brand-100 bg-brand-50/60 px-3 py-2.5">
            <p className="text-[11px] font-bold text-brand-700">
              {toFa(quote.offers_count)} پیشنهاد آماده بررسی است
            </p>
            <Link
              to={`/quote/mine/${quote.id}`}
              className="text-[11px] font-black text-brand-700"
            >
              مقایسه پیشنهادها ←
            </Link>
          </div>
        )}
      </div>
      <div className="border-t border-slate-100 px-4 py-2.5">
        <Link
          to={`/quote/mine/${quote.id}`}
          className="flex items-center justify-center text-xs font-bold text-brand-600"
        >
          مشاهده جزئیات و پیشنهادها
        </Link>
      </div>
    </article>
  );
}

function HistoryQuoteCard({ quote }: { quote: Quote }) {
  return (
    <Link
      to={`/quote/mine/${quote.id}`}
      className="flex items-start justify-between gap-3 rounded-2xl border border-slate-200 bg-white p-3.5 transition-colors hover:border-brand-200"
    >
      <div className="min-w-0">
        <div className="flex flex-wrap items-center gap-1.5">
          <QuoteStatusBadge quote={quote} />
          {quote.is_urgent && <Badge tone="amber">فوری</Badge>}
          {quote.accepted_offer && (
            <span className="text-[10px] text-slate-400">
              {quote.accepted_offer.business?.name}
            </span>
          )}
        </div>
        <p className="mt-1.5 truncate text-sm font-bold text-slate-900">{quote.title}</p>
        <p className="mt-0.5 line-clamp-1 text-[11px] text-slate-500">
          {quote.category?.name ?? "بدون دسته"} · {quote.address}
        </p>
      </div>
      <div className="shrink-0 text-left">
        <p className="text-[10px] text-slate-400">
          {quote.created_at ? formatJalali(quote.created_at) : ""}
        </p>
        <p className="mt-1 text-[10px] text-slate-400">{toFa(quote.offers_count)} پیشنهاد</p>
      </div>
    </Link>
  );
}

export function QuoteList() {
  const [showHistory, setShowHistory] = useState(true);
  const { data, error, isLoading } = useApi<{ items: Quote[] }>(
    ["quotes", "mine"],
    "/quotes/requests/mine",
  );

  const items = data?.items ?? [];
  const active = items.filter(isActiveQuote);
  const history = items.filter((quote) => !isActiveQuote(quote));
  const hasActive = active.length > 0;

  return (
    <section className="space-y-4">
      <header className="flex items-center justify-between gap-3">
        <div>
          <h1 className="text-lg font-black text-slate-900">استعلام قیمت من</h1>
          <p className="mt-1 text-xs text-slate-500">
            نیازتان را ثبت کنید و پیشنهاد کسب‌وکارهای محلی را مقایسه کنید.
          </p>
        </div>
        {!hasActive && (
          <Link
            to="/quote/new"
            className="inline-flex h-9 shrink-0 items-center rounded-xl bg-brand-600 px-3 text-xs font-bold text-white"
          >
            درخواست جدید
          </Link>
        )}
      </header>

      {isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}

      {!isLoading && !error && items.length === 0 && (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-brand-50 text-brand-600">
            <ClipboardIcon className="h-7 w-7" />
          </span>
          <p className="mt-4 text-sm font-black text-slate-900">هنوز درخواستی ثبت نکرده‌اید</p>
          <p className="mx-auto mt-2 max-w-xs text-xs leading-6 text-slate-500">
            نیاز خود را بنویسید تا کسب‌وکارهای مرتبط در بهبهان برای شما پیشنهاد قیمت
            بفرستند. شماره شما ناشناس می‌ماند.
          </p>
          <Link to="/quote/new" className="mt-5 inline-block">
            <Button>ثبت اولین درخواست</Button>
          </Link>
        </div>
      )}

      {active.map((quote) => (
        <ActiveQuoteCard key={quote.id} quote={quote} />
      ))}

      {hasActive && (
        <div className="rounded-2xl border border-slate-200 bg-white px-4 py-3 text-[11px] leading-6 text-slate-500">
          تا زمانی که یک درخواست فعال دارید، امکان ثبت درخواست جدید وجود ندارد. پس از
          انتخاب پیشنهاد یا لغو درخواست، می‌توانید درخواست تازه ثبت کنید.
        </div>
      )}

      {history.length > 0 && (
        <div className="space-y-2">
          <button
            type="button"
            onClick={() => setShowHistory((current) => !current)}
            className="flex w-full items-center justify-between rounded-2xl border border-slate-200 bg-white px-4 py-3"
          >
            <span className="text-xs font-bold text-slate-700">
              سابقه درخواست‌ها ({toFa(history.length)})
            </span>
            <span className="text-[10px] text-brand-600">
              {showHistory ? "پنهان کردن" : "نمایش"}
            </span>
          </button>
          {showHistory &&
            history.map((quote) => <HistoryQuoteCard key={quote.id} quote={quote} />)}
        </div>
      )}
    </section>
  );
}
