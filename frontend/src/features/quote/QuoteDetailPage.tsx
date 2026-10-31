import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { useMutation, useQueryClient } from "@tanstack/react-query";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { ConfirmSheet } from "@/components/ui/confirm-sheet";
import { RatingStars } from "@/components/ui/stars";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import { formatRating } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";
import type { Quote, QuoteOffer } from "./types";
import { DispatchProgress } from "./DispatchProgress";
import {
  OFFER_STATUS_LABELS,
  OFFER_STATUS_TONES,
  QUOTE_STATUS_LABELS,
  QUOTE_STATUS_TONES,
  formatToman,
  useCountdown,
} from "./quote-utils";
import { CheckIcon, ClockIcon, PhoneIcon, PinIcon, SparkIcon } from "./icons";

function OfferCard({
  offer,
  accepted,
  canAccept,
  onAccept,
}: {
  offer: QuoteOffer;
  accepted: boolean;
  canAccept: boolean;
  onAccept: () => void;
}) {
  const business = offer.business;
  return (
    <article
      className={cn(
        "rounded-2xl border bg-white p-4",
        accepted ? "border-brand-300 ring-2 ring-brand-100" : "border-slate-200",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2.5">
          <span className="flex h-10 w-10 shrink-0 items-center justify-center overflow-hidden rounded-xl bg-slate-100 text-lg">
            {business?.profile_image_url ? (
              <img src={business.profile_image_url} alt="" className="h-full w-full object-cover" />
            ) : (
              business?.category?.icon ?? "🏪"
            )}
          </span>
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-1.5">
              <p className="line-clamp-2 text-sm font-bold leading-6 text-slate-900">
                {business?.name ?? "کسب‌وکار"}
              </p>
              {business?.is_verified && <Badge tone="brand">تأییدشده</Badge>}
            </div>
            <div className="mt-1 flex items-center gap-1.5 text-[10px] text-slate-400">
              {(business?.rating_count ?? 0) > 0 ? (
                <>
                  <RatingStars rating={business?.rating_avg ?? 0} />
                  <span>
                    {formatRating(business?.rating_avg)} ({toFa(business?.rating_count ?? 0)})
                  </span>
                </>
              ) : (
                <span>کسب‌وکار تازه</span>
              )}
            </div>
          </div>
        </div>
        {accepted ? (
          <Badge tone="brand">انتخاب‌شده</Badge>
        ) : (
          <Badge tone={OFFER_STATUS_TONES[offer.status] ?? "slate"}>
            {offer.status === "pending" && canAccept
              ? "در انتظار انتخاب شما"
              : OFFER_STATUS_LABELS[offer.status] ?? offer.status}
          </Badge>
        )}
      </div>

      <div className="mt-3 flex items-end justify-between gap-3 rounded-xl bg-slate-50 px-3 py-2.5">
        <div>
          <p className="text-[10px] text-slate-400">مبلغ پیشنهادی</p>
          <p className="mt-0.5 text-base font-black text-brand-700">{formatToman(offer.price)}</p>
        </div>
        <span className="text-[11px] text-slate-500">{offer.unit || "کل کار"}</span>
      </div>

      {(offer.brand || offer.message) && (
        <div className="mt-3 space-y-1.5 text-[11px] leading-6">
          {offer.brand && (
            <p>
              <span className="text-slate-400">برند: </span>
              <span className="text-slate-700">{offer.brand}</span>
            </p>
          )}
          {offer.message && (
            <p className="rounded-xl bg-slate-50 px-3 py-2 text-slate-600">{offer.message}</p>
          )}
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center gap-2">
        {business?.slug && (
          <Link
            to={`/businesses/${business.slug}`}
            className="inline-flex h-9 items-center rounded-xl border border-slate-200 px-3 text-[11px] font-bold text-slate-600"
          >
            مشاهده کسب‌وکار
          </Link>
        )}
        {accepted && business?.phone_business && (
          <a
            href={`tel:${business.phone_business}`}
            className="inline-flex h-9 items-center gap-1.5 rounded-xl bg-brand-600 px-3 text-[11px] font-bold text-white"
          >
            <PhoneIcon className="h-3.5 w-3.5" />
            تماس
          </a>
        )}
        {!accepted && canAccept && offer.status === "pending" && (
          <Button size="sm" className="mr-auto" onClick={onAccept}>
            انتخاب این پیشنهاد
          </Button>
        )}
      </div>
    </article>
  );
}

export default function QuoteDetailPage() {
  const { id } = useParams<{ id: string }>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const [accepting, setAccepting] = useState<QuoteOffer | null>(null);
  const [cancelOpen, setCancelOpen] = useState(false);

  const query = useApi<Quote>(["quote", id], `/quotes/${id}`, { enabled: Boolean(id) });
  const quote = query.data;
  const countdown = useCountdown(quote?.expires_at);

  const acceptMutation = useMutation({
    mutationFn: (offer: QuoteOffer) =>
      api(`/quotes/offers/${offer.id}/accept`, { method: "PATCH" }),
    onSuccess: async () => {
      toast("پیشنهاد انتخاب شد. شماره تماس شما با این کسب‌وکار به اشتراک گذاشته شد.");
      setAccepting(null);
      await queryClient.invalidateQueries({ queryKey: ["quotes"] });
      await queryClient.invalidateQueries({ queryKey: ["quote", id] });
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const cancelMutation = useMutation({
    mutationFn: () =>
      api(`/quotes/requests/${id}/cancel`, { method: "POST" }),
    onSuccess: async () => {
      toast("درخواست لغو شد.");
      setCancelOpen(false);
      await queryClient.invalidateQueries({ queryKey: ["quotes"] });
      await queryClient.invalidateQueries({ queryKey: ["quote", id] });
    },
    onError: (error) => toast(errorMessage(error)),
  });

  if (query.isLoading) {
    return (
      <main className="flex min-h-[50dvh] items-center justify-center text-brand-600">
        <Spinner />
      </main>
    );
  }

  if (query.error || !quote) {
    return (
      <main className="mx-auto max-w-xl px-4 py-10 text-center">
        <p className="text-sm text-rose-600">
          {query.error ? errorMessage(query.error) : "درخواست پیدا نشد."}
        </p>
        <Link to="/quote/mine" className="mt-4 inline-block">
          <Button variant="outline" size="sm">
            بازگشت به درخواست‌ها
          </Button>
        </Link>
      </main>
    );
  }

  const offers = quote.offers ?? [];
  const accepted = offers.find((offer) => offer.id === quote.accepted_offer_id);
  const canAccept = quote.status === "active";

  return (
    <main className="mx-auto w-full max-w-xl space-y-4 px-4 py-4">
      <div className="flex items-center justify-between gap-2">
        <Link to="/quote/mine" className="text-xs font-bold text-brand-600">
          ← بازگشت به درخواست‌ها
        </Link>
        <Badge tone={QUOTE_STATUS_TONES[quote.status] ?? "slate"}>
          {QUOTE_STATUS_LABELS[quote.status] ?? quote.status}
        </Badge>
      </div>

      <section className="rounded-3xl border border-slate-200 bg-white p-4">
        <div className="flex flex-wrap items-center gap-2">
          {quote.category && (
            <span className="text-[11px] text-slate-400">
              {quote.category.icon} {quote.category.name}
              {quote.subcategory ? ` › ${quote.subcategory.name}` : ""}
            </span>
          )}
          {quote.is_urgent && <Badge tone="amber">فوری</Badge>}
        </div>
        <h1 className="mt-1 text-lg font-black text-slate-900">{quote.title}</h1>
        {quote.description && (
          <p className="mt-2 text-xs leading-6 text-slate-600">{quote.description}</p>
        )}

        <div className="mt-3 flex flex-wrap items-center gap-2">
          {quote.status === "active" && countdown && (
            <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2.5 py-1 text-[10px] font-medium text-amber-700">
              <ClockIcon className="h-3.5 w-3.5" />
              {countdown}
            </span>
          )}
          <span className="inline-flex items-center gap-1 rounded-full bg-slate-100 px-2.5 py-1 text-[10px] text-slate-600">
            <SparkIcon className="h-3.5 w-3.5" />
            {toFa(quote.offers_count)} پیشنهاد
          </span>
          {quote.created_at && (
            <span className="text-[10px] text-slate-400">{formatJalali(quote.created_at)}</span>
          )}
        </div>

        <div className="mt-3 flex items-start gap-2 rounded-xl bg-slate-50 px-3 py-2.5 text-[11px] leading-6 text-slate-500">
          <PinIcon className="mt-0.5 h-4 w-4 shrink-0 text-slate-400" />
          <span>
            {quote.address}
            {quote.neighborhood ? ` · ${quote.neighborhood}` : ""}
          </span>
        </div>
      </section>

      <DispatchProgress dispatch={quote.dispatch} />

      {quote.status === "accepted" && accepted && (
        <section className="rounded-2xl border border-brand-200 bg-brand-50 p-4">
          <div className="flex items-center gap-2 text-brand-700">
            <CheckIcon className="h-5 w-5" />
            <p className="text-sm font-black">پیشنهاد انتخاب شد</p>
          </div>
          <p className="mt-1 text-[11px] leading-6 text-brand-700/80">
            شماره تماس شما فقط برای این کسب‌وکار نمایش داده می‌شود.
          </p>
          <div className="mt-3 flex items-center justify-between gap-3 rounded-xl bg-white p-3">
            <div>
              <p className="text-sm font-bold text-slate-900">{accepted.business?.name}</p>
              <p className="mt-0.5 text-xs text-slate-500">{formatToman(accepted.price)}</p>
              {accepted.business?.phone_business && (
                <p className="mt-1 text-[11px] font-bold text-slate-600" dir="ltr">
                  {accepted.business.phone_business}
                </p>
              )}
            </div>
            {accepted.business?.phone_business && (
              <a
                href={`tel:${accepted.business.phone_business}`}
                className="inline-flex h-10 items-center gap-1.5 rounded-xl bg-brand-600 px-3 text-xs font-bold text-white"
              >
                <PhoneIcon className="h-4 w-4" />
                تماس
              </a>
            )}
          </div>
        </section>
      )}

      {(quote.status === "cancelled" || quote.status === "expired") && (
        <section className="rounded-2xl border border-slate-200 bg-white p-4 text-xs leading-6 text-slate-500">
          {quote.status === "cancelled"
            ? "این درخواست لغو شده است و پیشنهاددهندگان دیگر امکان ارسال پیشنهاد ندارند."
            : "مهلت این درخواست تمام شده است. برای دریافت پیشنهاد تازه، درخواست جدیدی ثبت کنید."}
        </section>
      )}

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-black text-slate-900">پیشنهادهای دریافتی</h2>
          {quote.status === "active" && (
            <button
              type="button"
              onClick={() => setCancelOpen(true)}
              className="text-[11px] font-bold text-rose-600"
            >
              لغو درخواست
            </button>
          )}
        </div>

        {offers.length === 0 && (
          <div className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center">
            <span className="mx-auto flex h-12 w-12 items-center justify-center rounded-2xl bg-slate-100 text-slate-400">
              <ClockIcon className="h-6 w-6" />
            </span>
            <p className="mt-3 text-sm font-bold text-slate-900">در انتظار پیشنهادها</p>
            <p className="mt-1 text-[11px] leading-6 text-slate-500">
              درخواست شما برای کسب‌وکارهای مرتبط ارسال شده است. پیشنهادها به‌محض رسیدن
              همین‌جا نمایش داده می‌شوند.
            </p>
          </div>
        )}

        {offers.map((offer) => (
          <OfferCard
            key={offer.id}
            offer={offer}
            accepted={offer.id === quote.accepted_offer_id}
            canAccept={canAccept}
            onAccept={() => setAccepting(offer)}
          />
        ))}
      </section>

      <ConfirmSheet
        open={accepting !== null}
        title="انتخاب پیشنهاد"
        description={
          accepting ? (
            <>
              پیشنهاد <b>{accepting.business?.name}</b> به مبلغ{" "}
              <b>{formatToman(accepting.price)}</b> انتخاب شود؟
              <br />
              با تأیید، شماره تماس شما برای این کسب‌وکار نمایش داده می‌شود و سایر
              پیشنهادها منقضی می‌شوند.
            </>
          ) : null
        }
        confirmLabel="تأیید و اشتراک شماره"
        loading={acceptMutation.isPending}
        onClose={() => setAccepting(null)}
        onConfirm={() => accepting && acceptMutation.mutate(accepting)}
      />

      <ConfirmSheet
        open={cancelOpen}
        title="لغو درخواست"
        description="با لغو این درخواست، همه پیشنهادهای در انتظار منقضی می‌شوند و امکان بازگردانی وجود ندارد. ادامه می‌دهید؟"
        confirmLabel="لغو درخواست"
        tone="rose"
        loading={cancelMutation.isPending}
        onClose={() => setCancelOpen(false)}
        onConfirm={() => cancelMutation.mutate()}
      />
    </main>
  );
}
