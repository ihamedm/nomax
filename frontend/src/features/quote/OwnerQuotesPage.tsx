import { useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { ConfirmSheet } from "@/components/ui/confirm-sheet";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import { formatRelative } from "@/lib/jalali";
import { useApi } from "@/lib/query";
import type { IncomingQuote, IncomingResponse } from "./types";
import {
  QUOTE_STATUS_LABELS,
  formatToman,
  useCountdown,
} from "./quote-utils";
import { OfferSheet } from "./OfferSheet";
import {
  ArchiveIcon,
  ClockIcon,
  PhoneIcon,
  PinIcon,
  SparkIcon,
  UsersIcon,
} from "./icons";

type Scope = "new" | "archive" | "customers";

const TABS: Array<{
  value: Scope;
  label: string;
  icon: (props: { className?: string }) => JSX.Element;
}> = [
  { value: "new", label: "جدید", icon: SparkIcon },
  { value: "customers", label: "مشتریان", icon: UsersIcon },
  { value: "archive", label: "بایگانی", icon: ArchiveIcon },
];

function UrgentDeadline({ quote }: { quote: IncomingQuote }) {
  const text = useCountdown(quote.expires_at);
  if (!text) return null;
  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-medium text-amber-700">
      <ClockIcon className="h-3.5 w-3.5" />
      {text}
    </span>
  );
}

function CustomerLine({ quote, showPhone }: { quote: IncomingQuote; showPhone?: boolean }) {
  const phone = quote.customer?.phone ?? quote.customer_phone;
  return (
    <div className="flex flex-wrap items-center gap-2 text-[10px] text-slate-400">
      <span className="inline-flex items-center gap-1">
        <UsersIcon className="h-3.5 w-3.5" />
        {quote.customer?.name || "کاربر نومکس"}
      </span>
      {quote.created_at && <span>· {formatRelative(quote.created_at)}</span>}
      {showPhone && phone && (
        <a
          href={`tel:${phone}`}
          className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 font-bold text-brand-700"
          dir="ltr"
        >
          <PhoneIcon className="h-3 w-3" />
          {phone}
        </a>
      )}
    </div>
  );
}

function NewRequestCard({
  quote,
  onOffer,
  onDecline,
}: {
  quote: IncomingQuote;
  onOffer: () => void;
  onDecline: () => void;
}) {
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <CustomerLine quote={quote} />
          <h2 className="mt-1.5 text-sm font-black text-slate-900">{quote.title}</h2>
          <p className="mt-1 line-clamp-2 text-[11px] leading-6 text-slate-500">
            {quote.description || "بدون توضیحات تکمیلی"}
          </p>
        </div>
        <div className="flex shrink-0 flex-col items-end gap-1.5">
          {quote.is_urgent && <Badge tone="amber">فوری</Badge>}
          {quote.category && (
            <span className="text-[10px] text-slate-400">
              {quote.category.icon} {quote.category.name}
            </span>
          )}
        </div>
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {quote.is_urgent && <UrgentDeadline quote={quote} />}
        <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] text-slate-600">
          <PinIcon className="h-3.5 w-3.5" />
          {quote.neighborhood || quote.address}
        </span>
        {quote.matching_businesses.length > 1 && (
          <span className="text-[10px] text-slate-400">
            {toFa(quote.matching_businesses.length)} کسب‌وکار مرتبط
          </span>
        )}
      </div>

      <div className="mt-4 flex gap-2">
        <Button type="button" className="flex-1" onClick={onOffer}>
          ارسال پیشنهاد
        </Button>
        <Button type="button" variant="outline" className="px-5 text-rose-600" onClick={onDecline}>
          رد
        </Button>
      </div>
    </article>
  );
}

function ArchiveRequestCard({ quote }: { quote: IncomingQuote }) {
  const offer = quote.my_offer;
  const isPending = offer?.status === "pending";
  const waiting = isPending && quote.status === "active";
  const lost = quote.status === "accepted" && offer?.status !== "accepted";
  const expired = quote.status === "expired" || quote.status === "cancelled";
  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <CustomerLine quote={quote} />
          <h2 className="mt-1.5 text-sm font-black text-slate-900">{quote.title}</h2>
          <p className="mt-1 line-clamp-1 text-[11px] text-slate-500">{quote.address}</p>
        </div>
        <Badge
          tone={
            offer?.status === "declined"
              ? "rose"
              : waiting
                ? "amber"
                : expired
                  ? "slate"
                  : "brand"
          }
        >
          {offer?.status === "declined"
            ? "رد شده توسط شما"
            : waiting
              ? "پیشنهاد ارسال شد"
              : lost
                ? "انتخاب نشد"
                : expired
                  ? QUOTE_STATUS_LABELS[quote.status] ?? "بسته شد"
                  : "پیشنهاد ارسال شد"}
        </Badge>
      </div>

      {offer && offer.price != null && (
        <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
          <div>
            <p className="text-[10px] text-slate-400">پیشنهاد شما</p>
            <p className="mt-0.5 text-sm font-black text-slate-800">{formatToman(offer.price)}</p>
          </div>
          <span className="text-[10px] text-slate-500">{offer.unit || "کل کار"}</span>
        </div>
      )}

      <p className="mt-2 text-[10px] leading-5 text-slate-400">
        {waiting
          ? "در انتظار انتخاب مشتری. در صورت انتخاب، اطلاعات تماس در تب مشتریان نمایش داده می‌شود."
          : lost
            ? "مشتری پیشنهاد کسب‌وکار دیگری را انتخاب کرده است."
            : expired
              ? "این درخواست بسته شده است و امکان ارسال پیشنهاد جدید وجود ندارد."
              : offer?.status === "declined"
                ? "شما این درخواست را رد کردید."
                : "پیشنهاد شما در این درخواست انتخاب نشد."}
      </p>
    </article>
  );
}

function CustomerCard({ quote }: { quote: IncomingQuote }) {
  const offer = quote.my_offer;
  const phone = quote.customer?.phone ?? quote.customer_phone;
  return (
    <article className="overflow-hidden rounded-2xl border border-brand-200 bg-white">
      <div className="h-1 bg-brand-500" />
      <div className="p-4">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <p className="text-sm font-black text-slate-900">{quote.customer?.name}</p>
              <Badge tone="brand">مشتری شما</Badge>
            </div>
            <div className="mt-1 flex flex-wrap items-center gap-2 text-[10px] text-slate-400">
              {phone && (
                <a
                  href={`tel:${phone}`}
                  className="font-bold text-slate-600"
                  dir="ltr"
                >
                  {phone}
                </a>
              )}
              {quote.created_at && <span>· {formatRelative(quote.created_at)}</span>}
            </div>
          </div>
          <p className="shrink-0 text-sm font-black text-brand-700">
            {formatToman(offer?.price)}
          </p>
        </div>

        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2.5">
          <p className="text-xs font-bold text-slate-800">{quote.title}</p>
          <p className="mt-1 flex items-start gap-1.5 text-[10px] leading-5 text-slate-500">
            <PinIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {quote.address}
          </p>
        </div>

        <div className="mt-3 flex items-center gap-2">
          {phone && (
            <a
              href={`tel:${phone}`}
              className="inline-flex h-10 flex-1 items-center justify-center gap-2 rounded-xl bg-brand-600 text-xs font-bold text-white"
            >
              <PhoneIcon className="h-4 w-4" />
              تماس با مشتری
            </a>
          )}
          {offer?.business?.slug && (
            <Link
              to={`/businesses/${offer.business.slug}`}
              className="inline-flex h-10 items-center justify-center rounded-xl border border-slate-200 px-3 text-[11px] font-bold text-slate-600"
            >
              کسب‌وکار
            </Link>
          )}
        </div>
      </div>
    </article>
  );
}

export function OwnerQuotesPage() {
  const [params, setParams] = useSearchParams();
  const rawScope = params.get("tab");
  const scope: Scope =
    rawScope === "archive" || rawScope === "customers" ? rawScope : "new";
  const queryClient = useQueryClient();
  const toast = useToast();
  const [offerQuote, setOfferQuote] = useState<IncomingQuote | null>(null);
  const [declining, setDeclining] = useState<IncomingQuote | null>(null);

  const query = useApi<IncomingResponse>(
    ["quotes", "incoming", scope],
    `/quotes/requests/incoming?scope=${scope}`,
  );
  const counts = query.data?.counts ?? { new: 0, archive: 0, customers: 0 };
  const items = query.data?.items ?? [];

  function setScope(next: Scope) {
    const nextParams = new URLSearchParams(params);
    if (next === "new") nextParams.delete("tab");
    else nextParams.set("tab", next);
    setParams(nextParams, { replace: true });
  }

  const declineMutation = useMutation({
    mutationFn: (quote: IncomingQuote) =>
      api(`/quotes/requests/${quote.id}/decline`, {
        method: "POST",
        body: JSON.stringify({ business_id: quote.matching_businesses[0]?.id }),
      }),
    onSuccess: async () => {
      toast("درخواست رد شد و به بایگانی منتقل شد.");
      setDeclining(null);
      await queryClient.invalidateQueries({ queryKey: ["quotes"] });
      setScope("archive");
    },
    onError: (error) => toast(errorMessage(error)),
  });

  async function afterOffer() {
    setOfferQuote(null);
    await queryClient.invalidateQueries({ queryKey: ["quotes"] });
    setScope("archive");
  }

  return (
    <section className="space-y-4">
      <header>
        <h1 className="text-lg font-black text-slate-900">مشتریان</h1>
        <p className="mt-1 text-xs text-slate-500">
          درخواست‌های قیمت دریافتی، پیشنهادهای ارسالی و مشتریان نهایی شما.
        </p>
      </header>

      <div className="rounded-2xl border border-slate-200 bg-white p-1.5">
        <div className="grid grid-cols-3 gap-1">
          {TABS.map((tab) => {
            const active = scope === tab.value;
            const count =
              tab.value === "new"
                ? counts.new
                : tab.value === "archive"
                  ? counts.archive
                  : counts.customers;
            return (
              <button
                key={tab.value}
                type="button"
                onClick={() => setScope(tab.value)}
                className={cn(
                  "relative flex flex-col items-center gap-1 rounded-xl px-2 py-2.5 text-[11px] transition-colors",
                  active
                    ? "bg-brand-50 font-bold text-brand-700"
                    : "text-slate-500 hover:bg-slate-50",
                )}
              >
                <tab.icon className="h-4 w-4" />
                <span>{tab.label}</span>
                {count > 0 && (
                  <span
                    className={cn(
                      "absolute left-2 top-1.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[9px] font-bold text-white",
                      tab.value === "new" ? "bg-rose-500" : "bg-slate-400",
                    )}
                  >
                    {toFa(count)}
                  </span>
                )}
              </button>
            );
          })}
        </div>
      </div>

      {query.isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {query.error && <p className="text-sm text-rose-600">{errorMessage(query.error)}</p>}

      {!query.isLoading && !query.error && items.length === 0 && (
        <div className="rounded-3xl border border-dashed border-slate-300 bg-white p-8 text-center">
          <span className="mx-auto flex h-14 w-14 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
            {scope === "customers" ? (
              <UsersIcon className="h-7 w-7" />
            ) : scope === "archive" ? (
              <ArchiveIcon className="h-7 w-7" />
            ) : (
              <SparkIcon className="h-7 w-7" />
            )}
          </span>
          <p className="mt-4 text-sm font-black text-slate-900">
            {scope === "new"
              ? "درخواست تازه‌ای ندارید"
              : scope === "archive"
                ? "بایگانی خالی است"
                : "هنوز مشتری نهایی ندارید"}
          </p>
          <p className="mx-auto mt-2 max-w-xs text-[11px] leading-6 text-slate-500">
            {scope === "new"
              ? "درخواست‌های هم‌دسته با کسب‌وکار تأییدشده شما در این بخش نمایش داده می‌شوند."
              : scope === "archive"
                ? "پیشنهادهای ارسال‌شده و درخواست‌های ردشده اینجا نگه داشته می‌شوند."
                : "پس از انتخاب پیشنهاد شما توسط مشتری، اطلاعات تماس او در این بخش نمایش داده می‌شود."}
          </p>
          {scope === "new" && (
            <Link to="/me/businesses" className="mt-4 inline-block text-xs font-bold text-brand-600">
              مشاهده کسب‌وکارهای من ←
            </Link>
          )}
        </div>
      )}

      <div className="space-y-2">
        {items.map((quote) =>
          scope === "new" ? (
            <NewRequestCard
              key={quote.id}
              quote={quote}
              onOffer={() => setOfferQuote(quote)}
              onDecline={() => setDeclining(quote)}
            />
          ) : scope === "customers" ? (
            <CustomerCard key={quote.id} quote={quote} />
          ) : (
            <ArchiveRequestCard key={quote.id} quote={quote} />
          ),
        )}
      </div>

      <OfferSheet
        open={offerQuote !== null}
        quote={offerQuote}
        onClose={() => setOfferQuote(null)}
        onSubmitted={() => void afterOffer()}
      />

      <ConfirmSheet
        open={declining !== null}
        title="رد درخواست"
        description="با رد این درخواست، دیگر امکان ارسال پیشنهاد برای آن را ندارید و درخواست به بایگانی منتقل می‌شود. ادامه می‌دهید؟"
        confirmLabel="رد درخواست"
        tone="rose"
        loading={declineMutation.isPending}
        onClose={() => setDeclining(null)}
        onConfirm={() => declining && declineMutation.mutate(declining)}
      />
    </section>
  );
}
