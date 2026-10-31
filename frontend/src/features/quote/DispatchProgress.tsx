import { cn } from "@/lib/cn";
import { toFa } from "@/lib/digits";
import type { QuoteDispatchSummary } from "./types";
import { useCountdown } from "./quote-utils";

const STATE_COPY: Record<
  QuoteDispatchSummary["state"],
  { title: string; hint: string; tone: "brand" | "amber" | "slate" | "rose" }
> = {
  pending: {
    title: "درخواست در صف ارسال است",
    hint: "به‌محض باز شدن پنجره ارسال، کسب‌وکارهای مناسب مطلع می‌شوند.",
    tone: "amber",
  },
  scheduled: {
    title: "ارسال در پنجره زمانی بعدی",
    hint: "ارسال خودکار در ساعات مجاز انجام می‌شود تا مزاحمتی برای کسب‌وکارها نباشد.",
    tone: "amber",
  },
  searching: {
    title: "در حال یافتن کسب‌وکار مناسب",
    hint: "هنوز کسب‌وکار تأییدشده‌ای در این دسته پیدا نشده؛ جست‌وجو ادامه دارد.",
    tone: "amber",
  },
  waiting_seen: {
    title: "درخواست برای کسب‌وکارها ارسال شد",
    hint: "در انتظار مشاهده و بررسی توسط صاحبان کسب‌وکار.",
    tone: "brand",
  },
  reviewing: {
    title: "کسب‌وکارها در حال بررسی درخواست هستند",
    hint: "به‌محض ثبت پیشنهاد، همین‌جا نمایش داده می‌شود.",
    tone: "brand",
  },
  offers: {
    title: "پیشنهاد دریافت شد",
    hint: "پیشنهادهای جدید را مقایسه کنید و مناسب‌ترین را انتخاب کنید.",
    tone: "brand",
  },
  exhausted: {
    title: "به همه کسب‌وکارهای موجود ارسال شد",
    hint: "درخواست شما فعال است؛ پیشنهادهای تازه همچنان پذیرفته می‌شوند.",
    tone: "slate",
  },
  disabled: {
    title: "ارسال خودکار غیرفعال است",
    hint: "مدیر سامانه ارسال خودکار استعلام را موقتاً متوقف کرده است.",
    tone: "rose",
  },
  closed: {
    title: "فرایند ارسال پایان یافته است",
    hint: "",
    tone: "slate",
  },
};

function Stage({
  label,
  count,
  done,
  active,
  last,
}: {
  label: string;
  count?: number;
  done: boolean;
  active: boolean;
  last?: boolean;
}) {
  return (
    <div className="relative flex flex-1 flex-col items-center gap-1.5 text-center">
      {!last && (
        <span
          aria-hidden
          className={cn(
            "absolute right-1/2 top-[13px] h-0.5 w-full",
            done ? "bg-brand-500" : "bg-slate-200",
          )}
        />
      )}
      <span
        className={cn(
          "relative z-10 flex h-7 w-7 items-center justify-center rounded-full border-2 text-[10px] font-black transition-colors",
          done
            ? "border-brand-500 bg-brand-500 text-white"
            : active
              ? "border-brand-400 bg-white text-brand-600"
              : "border-slate-200 bg-white text-slate-300",
        )}
      >
        {done ? "✓" : active ? <span className="h-2 w-2 animate-pulse rounded-full bg-brand-500" /> : "•"}
      </span>
      <span
        className={cn(
          "text-[10px] leading-4",
          done || active ? "font-bold text-slate-700" : "text-slate-400",
        )}
      >
        {label}
      </span>
      {typeof count === "number" && (
        <span className="rounded-full bg-slate-100 px-1.5 py-0.5 text-[9px] font-bold text-slate-500">
          {toFa(count)}
        </span>
      )}
    </div>
  );
}

export function DispatchProgress({
  dispatch,
  className,
}: {
  dispatch?: QuoteDispatchSummary | null;
  className?: string;
}) {
  const next = useCountdown(dispatch?.next_dispatch_at);
  if (!dispatch || dispatch.state === "closed") return null;

  const copy = STATE_COPY[dispatch.state] ?? STATE_COPY.pending;
  const delivered = dispatch.delivered_count > 0;
  const seen = dispatch.seen_count > 0;
  const offered = dispatch.offers_count > 0;
  const stage = offered ? 3 : seen ? 2 : delivered ? 1 : 0;
  const progress = [8, 36, 67, 100][stage];
  const activeStage = dispatch.state === "offers" ? -1 : Math.min(stage + 1, 3);

  return (
    <section
      className={cn(
        "overflow-hidden rounded-2xl border border-slate-200 bg-white",
        className,
      )}
      aria-label="وضعیت ارسال درخواست به کسب‌وکارها"
    >
      <div className="flex items-start gap-2.5 px-3.5 pt-3.5">
        <span className="relative mt-1 flex h-2.5 w-2.5 shrink-0">
          {copy.tone === "brand" && (
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-400 opacity-60" />
          )}
          <span
            className={cn(
              "relative inline-flex h-2.5 w-2.5 rounded-full",
              copy.tone === "brand"
                ? "bg-brand-500"
                : copy.tone === "amber"
                  ? "bg-amber-500"
                  : copy.tone === "rose"
                    ? "bg-rose-500"
                    : "bg-slate-400",
            )}
          />
        </span>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center justify-between gap-1.5">
            <p className="text-[11px] font-black text-slate-800">{copy.title}</p>
            {dispatch.round > 0 && dispatch.is_active && (
              <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[9px] font-medium text-slate-500">
                موج {toFa(dispatch.round)} از {toFa(dispatch.max_rounds)}
              </span>
            )}
          </div>
          <p className="mt-0.5 text-[10px] leading-5 text-slate-500">{copy.hint}</p>
        </div>
      </div>

      <div className="px-3.5 pb-3 pt-3">
        <div className="relative mb-2 h-1.5 overflow-hidden rounded-full bg-slate-100">
          <div
            className={cn(
              "h-full rounded-full transition-all duration-500",
              dispatch.state === "disabled" ? "bg-rose-300" : "bg-brand-500",
            )}
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="flex items-start">
          <Stage label="ثبت" done active={false} />
          <Stage
            label="ارسال"
            count={dispatch.delivered_count}
            done={delivered}
            active={!delivered && activeStage === 1}
          />
          <Stage
            label="مشاهده"
            count={dispatch.seen_count}
            done={seen}
            active={delivered && !seen && activeStage === 2}
          />
          <Stage
            label="پیشنهاد"
            count={dispatch.offers_count}
            done={offered}
            active={seen && !offered && activeStage === 3}
            last
          />
        </div>

        <div className="mt-3 flex flex-wrap items-center justify-between gap-1.5 border-t border-slate-100 pt-2 text-[9px] text-slate-400">
          <span>
            {dispatch.delivered_count > 0
              ? `${toFa(dispatch.delivered_count)} کسب‌وکار مطلع شدند`
              : "هنوز ارسالی انجام نشده است"}
          </span>
          {dispatch.next_dispatch_at && dispatch.is_active && (
            <span className="font-medium text-brand-600">
              {dispatch.state === "scheduled" ? "شروع ارسال " : "ارسال دور بعدی "}
              {next || "به‌زودی"}
            </span>
          )}
        </div>
      </div>
    </section>
  );
}
