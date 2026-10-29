import { useEffect, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { RatingStars } from "@/components/ui/stars";
import { useToast } from "@/components/ui/toast";
import {
  OWNER_REVIEWS_KEY,
  type OwnerReview,
  type OwnerReviewList,
} from "@/features/reviews/useOwnerReviewBadge";
import { api, errorMessage } from "@/lib/api";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";

function statusMeta(review: OwnerReview) {
  if (review.is_private) {
    return { label: "خصوصی — فقط شما", tone: "sky" as const };
  }
  if (review.status === "approved") {
    return { label: "تأییدشده و منتشرشده", tone: "brand" as const };
  }
  return { label: "در انتظار تأیید", tone: "amber" as const };
}

function OwnerReviewCard({ review }: { review: OwnerReview }) {
  const toast = useToast();
  const queryClient = useQueryClient();
  const [replyOpen, setReplyOpen] = useState(false);
  const [replyText, setReplyText] = useState(review.reply ?? "");
  const meta = statusMeta(review);

  function invalidate() {
    return queryClient.invalidateQueries({ queryKey: ["reviews"] });
  }

  const moderate = useMutation({
    mutationFn: (next: string) =>
      api(`/businesses/reviews/${review.id}/status`, {
        method: "PATCH",
        body: JSON.stringify({ status: next }),
      }),
    onSuccess: async (_data, next) => {
      toast(next === "approved" ? "نظر تأیید و منتشر شد." : "نظر رد شد.");
      await invalidate();
    },
    onError: (error) => toast(errorMessage(error)),
  });

  const submitReply = useMutation({
    mutationFn: () =>
      api(`/reviews/${review.id}/reply`, {
        method: "POST",
        body: JSON.stringify({ reply: replyText.trim() }),
      }),
    onSuccess: async () => {
      toast("پاسخ شما ثبت شد.");
      setReplyOpen(false);
      await invalidate();
    },
    onError: (error) => toast(errorMessage(error)),
  });

  return (
    <article className="rounded-2xl border border-slate-200 bg-white p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <Link
            to={`/businesses/${review.business_slug}`}
            className="truncate text-sm font-bold text-slate-900 hover:text-brand-600"
          >
            {review.business_name}
          </Link>
          <p className="mt-1 text-[11px] text-slate-500">{review.author_name || "کاربر نومکس"}</p>
        </div>
        <Badge tone={meta.tone}>{meta.label}</Badge>
      </div>

      <div className="mt-3 flex items-center justify-between">
        <RatingStars rating={review.rating} />
        <span className="text-[10px] text-slate-400">
          {review.created_at ? formatJalali(review.created_at) : ""}
        </span>
      </div>

      {review.text && (
        <p className="mt-2 whitespace-pre-line text-xs leading-6 text-slate-600">{review.text}</p>
      )}

      {review.is_private ? (
        <p className="mt-3 rounded-xl bg-sky-50 px-3 py-2 text-[11px] leading-5 text-sky-700">
          این نظر خصوصی است، در صفحه عمومی نمایش داده نمی‌شود و نیازی به تأیید مدیر ندارد.
        </p>
      ) : review.status === "pending" ? (
        <p className="mt-3 rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800">
          این نظر پس از تأیید شما یا مدیر در صفحه عمومی کسب‌وکار نمایش داده می‌شود.
        </p>
      ) : null}

      {review.reply && !replyOpen && (
        <div className="mt-3 rounded-xl bg-slate-50 px-3 py-2">
          <p className="text-[10px] font-bold text-slate-500">پاسخ شما</p>
          <p className="mt-1 text-[11px] leading-5 text-slate-600">{review.reply}</p>
        </div>
      )}

      {replyOpen && (
        <div className="mt-3 space-y-2">
          <textarea
            value={replyText}
            onChange={(event) => setReplyText(event.target.value)}
            rows={3}
            maxLength={250}
            placeholder="پاسخ خود را بنویسید..."
            className="w-full rounded-xl border border-slate-200 px-3 py-2 text-xs leading-6 outline-none focus:border-brand-400"
          />
          <div className="flex items-center justify-between">
            <span className="text-[10px] text-slate-400">{replyText.length}/250</span>
            <div className="flex gap-2">
              <Button size="sm" variant="ghost" onClick={() => setReplyOpen(false)}>
                انصراف
              </Button>
              <Button
                size="sm"
                loading={submitReply.isPending}
                disabled={!replyText.trim()}
                onClick={() => submitReply.mutate()}
              >
                ثبت پاسخ
              </Button>
            </div>
          </div>
        </div>
      )}

      <div className="mt-3 flex flex-wrap items-center justify-between gap-2 border-t border-slate-100 pt-3">
        <div className="flex gap-2">
          {!review.is_private && review.status !== "approved" && (
            <Button
              size="sm"
              loading={moderate.isPending}
              onClick={() => moderate.mutate("approved")}
            >
              تأیید نظر
            </Button>
          )}
          {!review.is_private && review.status !== "rejected" && (
            <Button
              size="sm"
              variant="outline"
              disabled={moderate.isPending}
              onClick={() => moderate.mutate("rejected")}
            >
              رد نظر
            </Button>
          )}
        </div>
        {!replyOpen && (
          <button
            type="button"
            className="text-[11px] text-brand-600"
            onClick={() => {
              setReplyText(review.reply ?? "");
              setReplyOpen(true);
            }}
          >
            {review.reply ? "ویرایش پاسخ" : "پاسخ به نظر"}
          </button>
        )}
      </div>
    </article>
  );
}

export default function MeReviewsPage() {
  const queryClient = useQueryClient();
  const markedRef = useRef(false);
  const { data, error, isLoading } = useApi<OwnerReviewList>(OWNER_REVIEWS_KEY, "/me/reviews");

  const markSeen = useMutation({
    mutationFn: () => api("/me/reviews/mark-seen", { method: "PATCH" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reviews"] }),
  });

  useEffect(() => {
    if (!data || data.unread_count <= 0 || markedRef.current) return;
    markedRef.current = true;
    markSeen.mutate();
  }, [data, markSeen]);

  return (
    <section className="space-y-3">
      <header>
        <h1 className="text-lg font-black text-slate-900">نظرات کسب‌وکار</h1>
        <p className="mt-1 text-xs leading-6 text-slate-500">
          نظرات در انتظار تأیید و نظرات خصوصی مشتریان را اینجا می‌بینید. می‌توانید نظرات
          عمومی را تأیید یا رد کنید و به آن‌ها پاسخ دهید. نظرات خصوصی در صفحه عمومی نمایش داده
          نمی‌شوند.
        </p>
      </header>

      {isLoading && (
        <div className="flex justify-center py-16 text-brand-600">
          <Spinner />
        </div>
      )}
      {error && <p className="text-sm text-rose-600">{errorMessage(error)}</p>}
      {!isLoading && !error && data?.items.length === 0 && (
        <p className="rounded-2xl border border-dashed border-slate-300 bg-white p-8 text-center text-sm text-slate-500">
          هنوز نظری برای کسب‌وکارهای شما ثبت نشده است.
        </p>
      )}

      {data?.items.map((review) => (
        <OwnerReviewCard key={review.id} review={review} />
      ))}
    </section>
  );
}
