import { useEffect, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { normalizeDigits, toFa } from "@/lib/digits";
import { formatToman, OFFER_UNITS } from "./quote-utils";
import { PinIcon } from "./icons";
import type { IncomingQuote } from "./types";

interface OfferSheetProps {
  open: boolean;
  quote: IncomingQuote | null;
  onClose: () => void;
  onSubmitted: () => void;
}

const MAX_MESSAGE = 1000;

export function OfferSheet({ open, quote, onClose, onSubmitted }: OfferSheetProps) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [businessId, setBusinessId] = useState("");
  const [price, setPrice] = useState("");
  const [unit, setUnit] = useState("کل کار");
  const [brand, setBrand] = useState("");
  const [message, setMessage] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!open) return;
    setBusinessId(quote?.matching_businesses[0]?.id ?? "");
    setPrice("");
    setUnit("کل کار");
    setBrand("");
    setMessage("");
    setError(null);
  }, [open, quote]);

  if (!quote) return null;

  const numericPrice = Number(normalizeDigits(price));
  const preview = Number.isFinite(numericPrice) && numericPrice > 0
    ? formatToman(numericPrice)
    : null;

  async function submit() {
    if (!businessId) {
      setError("کسب‌وکار پیشنهاددهنده را انتخاب کنید.");
      return;
    }
    if (!Number.isFinite(numericPrice) || numericPrice <= 0) {
      setError("مبلغ پیشنهادی را به تومان و بزرگ‌تر از صفر وارد کنید.");
      return;
    }
    setLoading(true);
    setError(null);
    try {
      await api("/quotes/offers", {
        method: "POST",
        body: JSON.stringify({
          request_id: quote?.id,
          business_id: businessId,
          price: numericPrice,
          unit,
          brand: brand.trim() || null,
          message: message.trim() || null,
        }),
      });
      await queryClient.invalidateQueries({ queryKey: ["quotes"] });
      toast("پیشنهاد شما ارسال شد. نتیجه را از بخش مشتریان پیگیری کنید.");
      onSubmitted();
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setLoading(false);
    }
  }

  return (
    <BottomSheet open={open} onClose={onClose} title="ارسال پیشنهاد قیمت">
      <div className="space-y-4">
        <div className="rounded-2xl bg-slate-50 p-3.5">
          <p className="text-sm font-bold text-slate-900">{quote.title}</p>
          <p className="mt-1 line-clamp-2 text-[11px] leading-6 text-slate-500">
            {quote.description || "بدون توضیحات تکمیلی"}
          </p>
          <p className="mt-2 flex items-start gap-1.5 text-[10px] leading-5 text-slate-400">
            <PinIcon className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            {quote.address}
          </p>
        </div>

        {quote.matching_businesses.length > 1 && (
          <div>
            <label className="mb-1.5 block text-xs font-bold text-slate-700">
              از طرف کسب‌وکار
            </label>
            <select
              value={businessId}
              onChange={(event) => setBusinessId(event.target.value)}
              className="h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
            >
              {quote.matching_businesses.map((business) => (
                <option key={business.id} value={business.id}>
                  {business.name}
                </option>
              ))}
            </select>
          </div>
        )}

        <div>
          <label className="mb-1.5 block text-xs font-bold text-slate-700">
            مبلغ پیشنهادی (تومان)
          </label>
          <Input
            value={price}
            onChange={(event) =>
              setPrice(normalizeDigits(event.target.value).replace(/\D/g, "").slice(0, 12))
            }
            placeholder="مثلاً ۲۵۰۰۰۰۰"
            inputMode="numeric"
            dir="ltr"
          />
          {preview && (
            <p className="mt-1.5 text-[10px] text-slate-400">
              مبلغ: <span className="font-bold text-slate-600">{preview}</span>
            </p>
          )}
        </div>

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="mb-1.5 block text-xs font-bold text-slate-700">
              واحد قیمت
            </label>
            <select
              value={unit}
              onChange={(event) => setUnit(event.target.value)}
              className="h-12 w-full rounded-xl border border-slate-200 bg-white px-3 text-sm text-slate-700"
            >
              {OFFER_UNITS.map((item) => (
                <option key={item} value={item}>
                  {item}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-bold text-slate-700">
              برند (اختیاری)
            </label>
            <Input
              value={brand}
              onChange={(event) => setBrand(event.target.value.slice(0, 120))}
              placeholder="مثلاً سامسونگ"
            />
          </div>
        </div>

        <div>
          <div className="mb-1.5 flex items-center justify-between">
            <label className="text-xs font-bold text-slate-700">
              توضیح برای مشتری (اختیاری)
            </label>
            <span className="text-[10px] text-slate-400">
              {toFa(message.length)} از {toFa(MAX_MESSAGE)}
            </span>
          </div>
          <textarea
            rows={3}
            value={message}
            onChange={(event) => setMessage(event.target.value.slice(0, MAX_MESSAGE))}
            placeholder="زمان مراجعه، گارانتی، شرایط پرداخت…"
            className="w-full resize-none rounded-xl border border-slate-200 bg-white px-4 py-3 text-sm leading-6 text-slate-900 placeholder:text-slate-400 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>

        <div className="rounded-xl border border-dashed border-slate-200 px-3 py-2 text-[10px] leading-5 text-slate-500">
          شماره تماس مشتری تا زمانی که پیشنهاد شما را انتخاب نکند نمایش داده نمی‌شود.
          برای هر درخواست فقط یک پیشنهاد می‌توانید ثبت کنید.
        </div>

        {error && <p className="text-xs leading-5 text-rose-600">{error}</p>}

        <Button type="button" className="h-12 w-full" loading={loading} onClick={submit}>
          ارسال پیشنهاد
        </Button>
      </div>
    </BottomSheet>
  );
}
