import { useEffect, useState, type FormEvent } from "react";

import { BottomSheet } from "@/components/ui/bottom-sheet";
import { Button } from "@/components/ui/button";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";

const STAR_LABELS = ["خیلی بد", "ضعیف", "متوسط", "خوب", "عالی"];

interface ReviewSheetProps {
  open: boolean;
  businessName: string;
  businessSlug: string;
  onClose: () => void;
  onSubmitted: () => void;
}

export function ReviewSheet({
  open,
  businessName,
  businessSlug,
  onClose,
  onSubmitted,
}: ReviewSheetProps) {
  const toast = useToast();
  const [rating, setRating] = useState(0);
  const [text, setText] = useState("");
  const [isPrivate, setIsPrivate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (!open) return;
    setRating(0);
    setText("");
    setIsPrivate(false);
    setError(null);
    setSubmitting(false);
  }, [open]);

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (rating < 1) {
      setError("برای ثبت نظر، امتیاز خود را انتخاب کنید.");
      return;
    }
    setSubmitting(true);
    setError(null);
    try {
      const result = await api<{ status: string; is_private: boolean }>(
        `/businesses/${encodeURIComponent(businessSlug)}/reviews`,
        {
          method: "POST",
          body: JSON.stringify({
            rating,
            text: text.trim() || null,
            is_private: isPrivate,
          }),
        }
      );
      toast(
        result.is_private
          ? "نظر خصوصی شما ثبت شد و فقط مالک کسب‌وکار آن را می‌بیند."
          : "نظر شما ثبت شد و پس از تأیید مدیر نمایش داده می‌شود."
      );
      onSubmitted();
      onClose();
    } catch (submitError) {
      setError(errorMessage(submitError));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <BottomSheet
      open={open}
      onClose={onClose}
      title={`ثبت نظر برای ${businessName}`}
    >
      <form onSubmit={submit} className="space-y-4">
        <div>
          <p className="text-xs font-bold text-slate-700">امتیاز شما</p>
          <div
            className="mt-2 flex items-center justify-center gap-2"
            dir="ltr"
          >
            {[1, 2, 3, 4, 5].map((value) => (
              <button
                key={value}
                type="button"
                aria-label={`${value} از ۵ — ${STAR_LABELS[value - 1]}`}
                aria-pressed={rating >= value}
                onClick={() => setRating(value)}
                className={
                  rating >= value
                    ? "px-1 text-3xl leading-none text-amber-500 transition-transform active:scale-95"
                    : "px-1 text-3xl leading-none text-slate-300 transition-transform active:scale-95"
                }
              >
                ★
              </button>
            ))}
          </div>
          <p className="mt-2 text-center text-[11px] text-slate-500">
            {rating > 0
              ? STAR_LABELS[rating - 1]
              : "یکی از ستاره‌ها را انتخاب کنید"}
          </p>
        </div>

        <div>
          <label
            htmlFor="review-text"
            className="text-xs font-bold text-slate-700"
          >
            متن نظر{" "}
            <span className="font-normal text-slate-400">(اختیاری)</span>
          </label>
          <textarea
            id="review-text"
            value={text}
            onChange={(event) => setText(event.target.value)}
            rows={4}
            maxLength={300}
            placeholder="تجربه‌تان از این کسب‌وکار را بنویسید..."
            className="mt-1 w-full rounded-xl border border-slate-200 px-3 py-2 text-sm leading-6 outline-none focus:border-brand-400"
          />
          <p className="mt-1 text-left text-[10px] text-slate-400" dir="ltr">
            {text.length}/300
          </p>
        </div>

        <label className="flex cursor-pointer items-start gap-3 rounded-2xl border border-slate-200 bg-slate-50 p-3">
          <input
            type="checkbox"
            checked={isPrivate}
            onChange={(event) => setIsPrivate(event.target.checked)}
            className="mt-0.5 h-4 w-4 accent-brand-600"
          />
          <span>
            <span className="block text-xs font-bold text-slate-800">
              نظر خصوصی باشد
            </span>
            <span className="mt-1 block text-[11px] leading-5 text-slate-500">
              نظر خصوصی برای عموم نمایش داده نمی‌شود و فقط مالک کسب‌وکار آن را
              می‌بیند.
            </span>
          </span>
        </label>

        {error && (
          <p className="rounded-xl bg-rose-50 px-3 py-2 text-xs leading-5 text-rose-700">
            {error}
          </p>
        )}

        <Button type="submit" className="w-full" loading={submitting}>
          ثبت نظر
        </Button>
      </form>
    </BottomSheet>
  );
}
