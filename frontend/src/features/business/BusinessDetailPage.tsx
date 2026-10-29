import { useEffect, useMemo, useRef, useState, type ReactNode } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { RatingStars } from "@/components/ui/stars";
import { useToast } from "@/components/ui/toast";
import { api, errorMessage } from "@/lib/api";
import { cn } from "@/lib/cn";
import { fa, formatPhone, formatRating } from "@/lib/format";
import { formatJalali } from "@/lib/jalali";
import { useApi } from "@/lib/query";
import { returnPath } from "@/lib/auth-redirect";
import { useAuth } from "@/stores/auth";
import { LoginRequiredSheet } from "@/features/auth/LoginRequiredSheet";
import { NeshanMap, type MapMarker } from "@/features/map/NeshanMap";
import { ReviewSheet } from "@/features/reviews/ReviewSheet";
import type { BusinessDetail } from "@/types";

function ActionLink({
  href,
  children,
  tone = "outline",
}: {
  href: string;
  children: ReactNode;
  tone?: "outline" | "primary";
}) {
  return (
    <a
      href={href}
      target={href.startsWith("tel:") ? undefined : "_blank"}
      rel={href.startsWith("tel:") ? undefined : "noreferrer"}
      className={
        tone === "primary"
          ? "inline-flex h-11 items-center justify-center gap-2 rounded-xl bg-brand-600 px-4 text-sm font-medium text-white"
          : "inline-flex h-11 items-center justify-center gap-2 rounded-xl border border-slate-200 bg-white px-4 text-sm font-medium text-slate-700"
      }
    >
      {children}
    </a>
  );
}

function myReviewBadge(review: NonNullable<BusinessDetail["my_review"]>) {
  if (review.is_private) return { label: "نظر خصوصی", tone: "sky" as const };
  if (review.status === "approved") return { label: "نظر شما منتشر شد", tone: "brand" as const };
  if (review.status === "rejected") return { label: "نظر رد شد", tone: "rose" as const };
  return { label: "در انتظار تأیید", tone: "amber" as const };
}

export function BusinessDetailPage() {
  const { slug } = useParams<{ slug: string }>();
  const queryClient = useQueryClient();
  const toast = useToast();
  const navigate = useNavigate();
  const location = useLocation();
  const user = useAuth((state) => state.user);
  const ready = useAuth((state) => state.ready);
  const detailQuery = useApi<BusinessDetail>(
    ["business", slug],
    `/businesses/${encodeURIComponent(slug ?? "")}`,
    { enabled: Boolean(slug) },
  );
  const business = detailQuery.data ?? null;
  const loading = detailQuery.isLoading;
  const error = detailQuery.error ? errorMessage(detailQuery.error) : null;
  const saved = Boolean(business?.is_saved);
  const [reviewOpen, setReviewOpen] = useState(false);
  const [loginPrompt, setLoginPrompt] = useState<"review" | "save" | null>(null);
  const reviewIntentHandled = useRef(false);

  const saveMutation = useMutation({
    mutationFn: () => {
      if (!business) return Promise.resolve();
      return api(`/me/bookmarks/${business.id}`, { method: saved ? "DELETE" : "POST" });
    },
    onSuccess: () => {
      queryClient.setQueryData<BusinessDetail>(["business", slug], (current) =>
        current ? { ...current, is_saved: !saved } : current,
      );
      void queryClient.invalidateQueries({ queryKey: ["me", "bookmarks"] });
      toast(saved ? "از ذخیره‌شده‌ها حذف شد." : "کسب‌وکار ذخیره شد.");
    },
    onError: (saveError) => toast(errorMessage(saveError)),
  });

  const reviewParams = new URLSearchParams(location.search);
  reviewParams.set("review", "1");
  const reviewNext = `${location.pathname}?${reviewParams.toString()}`;
  const currentPath = returnPath(location);

  // Navigating between business pages keeps this component mounted, so reset
  // the one-shot intent flag when the slug changes.
  useEffect(() => {
    reviewIntentHandled.current = false;
  }, [slug]);

  // The login sheet hands the review intent back through router state. Open
  // the review sheet only after hydration and only when the user can review,
  // then clear the one-shot state without changing the URL.
  const openReviewIntent = Boolean(
    (location.state as { openReview?: boolean } | null)?.openReview,
  );
  useEffect(() => {
    if (!openReviewIntent || reviewIntentHandled.current) return;
    if (!ready || detailQuery.isLoading) return;

    reviewIntentHandled.current = true;
    if (!user) {
      setLoginPrompt("review");
    } else if (business && !business.is_owner && !business.my_review) {
      setReviewOpen(true);
    }
    navigate(`${location.pathname}${location.search}`, { replace: true, state: null });
  }, [
    business,
    detailQuery.isLoading,
    location.pathname,
    location.search,
    navigate,
    openReviewIntent,
    ready,
    user,
  ]);

  function requestReview() {
    if (!ready) return;
    if (!user) {
      setLoginPrompt("review");
      return;
    }
    setReviewOpen(true);
  }

  function requestSave() {
    if (!ready) return;
    if (!user) {
      setLoginPrompt("save");
      return;
    }
    saveMutation.mutate();
  }

  const mapMarkers = useMemo<MapMarker[]>(() => {
    if (!business?.geo) return [];
    return [
      {
        id: business.id,
        lat: business.geo.lat,
        lng: business.geo.lng,
        title: business.name,
        subtitle: business.address,
      },
    ];
  }, [business]);

  const instagramHandle = business?.instagram?.replace(/^@/, "").replace(/[^A-Za-z0-9._]/g, "");
  const callNumber = business?.phone_business
    ? `tel:0${business.phone_business.replace(/^0/, "")}`
    : null;
  const neshanLink = business?.geo
    ? `https://neshan.org/maps/@${business.geo.lat},${business.geo.lng},16z`
    : null;

  return (
    <main className="mx-auto min-h-[100dvh] w-full max-w-xl pb-16">
      <header className="sticky top-14 z-20 flex items-center justify-between gap-2 border-b border-slate-200 bg-white/95 px-4 py-3 backdrop-blur">
        <p className="text-sm font-bold text-slate-800">جزئیات کسب‌وکار</p>
        {business?.is_owner && (
          <Link to={`/businesses/${business.id}/edit`} className="text-xs text-brand-600">
            ویرایش اطلاعات
          </Link>
        )}
      </header>

      {loading && (
        <div className="flex justify-center py-24 text-brand-600">
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <div className="px-4 py-10">
          <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-center text-sm text-rose-700">
            <p>{error}</p>
            <Link to="/search" className="mt-4 inline-block">
              <Button size="sm" variant="outline">
                بازگشت به جستجو
              </Button>
            </Link>
          </div>
        </div>
      )}

      {!loading && !error && business && (
        <div className="space-y-4 px-4 pt-4">
          {business.status === "rejected" && (
            <section
              role="alert"
              className="rounded-2xl border border-rose-200 bg-rose-50 p-4 text-rose-800"
            >
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="rose">ردشده</Badge>
                <p className="text-sm font-bold">این کسب‌وکار توسط مدیر رد شده است.</p>
              </div>
              <p className="mt-3 rounded-xl bg-white/70 px-3 py-2 text-xs leading-6 text-rose-700">
                <span className="font-bold">دلیل رد: </span>
                {business.rejection_reason || "دلیلی ثبت نشده است."}
              </p>
              <p className="mt-3 text-[11px] leading-5 text-rose-600">
                {business.is_owner
                  ? "اطلاعات کسب‌وکار را اصلاح کنید تا دوباره برای بررسی مدیر ارسال شود."
                  : "این کسب‌وکار تا اصلاح اطلاعات برای کاربران نمایش داده نمی‌شود."}
              </p>
              {business.is_owner && (
                <Link to={`/businesses/${business.id}/edit`} className="mt-4 inline-block">
                  <Button size="sm">اصلاح و ارسال دوباره</Button>
                </Link>
              )}
            </section>
          )}

          {business.status === "pending" && (
            <section className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-amber-800">
              <div className="flex flex-wrap items-center gap-2">
                <Badge tone="amber">در انتظار تأیید</Badge>
                <p className="text-sm font-bold">این کسب‌وکار در صف بررسی مدیر است.</p>
              </div>
              <p className="mt-2 text-[11px] leading-5 text-amber-700">
                {business.is_owner
                  ? "تا زمان تأیید، این صفحه فقط برای شما و مدیران قابل مشاهده است. با ویرایش، اطلاعات به‌روز شده و دوباره ارسال می‌شود."
                  : "این صفحه تا تأیید مدیر برای کاربران نمایش داده نمی‌شود."}
              </p>
              {business.is_owner && (
                <Link to={`/businesses/${business.id}/edit`} className="mt-3 inline-block">
                  <Button size="sm" variant="outline">
                    ویرایش اطلاعات
                  </Button>
                </Link>
              )}
            </section>
          )}

          <section className="overflow-hidden rounded-3xl bg-gradient-to-l from-brand-600 to-brand-500 p-5 text-white">
            <div className="flex items-start gap-4">
              <div className="flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-2xl bg-white/15 text-4xl">
                {business.profile_image_url ? (
                  <img
                    src={business.profile_image_url}
                    alt=""
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span aria-hidden>{business.category?.icon ?? "🏪"}</span>
                )}
              </div>
              <div className="min-w-0 flex-1">
                <h1 className="text-xl font-black leading-8">{business.name}</h1>
                <p className="mt-1 text-xs text-white/75">
                  {business.category?.name}
                  {business.subcategory ? ` · ${business.subcategory.name}` : ""}
                </p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {business.status === "rejected" && (
                    <span className="rounded-full bg-rose-500/40 px-2.5 py-1 text-[11px] text-white">
                      ردشده
                    </span>
                  )}
                  {business.status === "pending" && (
                    <span className="rounded-full bg-amber-300/25 px-2.5 py-1 text-[11px] text-amber-100">
                      در انتظار تأیید
                    </span>
                  )}
                  {business.is_verified && (
                    <span className="rounded-full bg-white/15 px-2.5 py-1 text-[11px]">تأیید شده</span>
                  )}
                  {business.is_24h && (
                    <span className="rounded-full bg-amber-300/20 px-2.5 py-1 text-[11px] text-amber-100">
                      ۲۴ ساعته
                    </span>
                  )}
                </div>
              </div>
            </div>

            <p className="mt-4 text-sm leading-6 text-white/85">{business.short_description}</p>

            <div className="mt-4 flex items-center justify-between rounded-2xl bg-white/10 px-4 py-3">
              <div>
                <p className="text-[11px] text-white/60">امتیاز کاربران</p>
                <p className="mt-1 text-lg font-black">
                  ★ {formatRating(business.rating_avg)}
                  <span className="mr-1 text-xs font-normal text-white/60">
                    از {fa(business.rating_count)} نظر
                  </span>
                </p>
              </div>
              <Badge tone="brand" className="bg-white/15 text-white">
                {business.rating_count > 0 ? "امتیاز ثبت‌شده" : "بدون نظر"}
              </Badge>
            </div>
          </section>

          <section className="grid grid-cols-2 gap-2">
            {callNumber ? (
              <ActionLink href={callNumber} tone="primary">
                📞 تماس با کسب‌وکار
              </ActionLink>
            ) : (
              <span className="inline-flex h-11 items-center justify-center rounded-xl bg-slate-100 text-xs text-slate-400">
                شماره تماس ثبت نشده
              </span>
            )}
            {neshanLink ? (
              <ActionLink href={neshanLink}>🧭 مسیریابی در نشان</ActionLink>
            ) : (
              <span className="inline-flex h-11 items-center justify-center rounded-xl bg-slate-100 text-xs text-slate-400">
                موقعیت ثبت نشده
              </span>
            )}
            {instagramHandle && (
              <ActionLink href={`https://instagram.com/${instagramHandle}`}>
                اینستاگرام @{instagramHandle}
              </ActionLink>
            )}
            {business.phone_business && (
              <div className="flex h-11 items-center justify-center rounded-xl border border-slate-200 bg-white px-3 text-xs text-slate-600">
                <span dir="ltr">{formatPhone(business.phone_business)}</span>
              </div>
            )}
            <button
              type="button"
              onClick={requestSave}
              disabled={saveMutation.isPending}
              className={cn(
                "inline-flex h-11 items-center justify-center gap-2 rounded-xl border px-4 text-sm font-medium transition-colors disabled:opacity-60",
                saved
                  ? "border-brand-200 bg-brand-50 text-brand-700"
                  : "border-slate-200 bg-white text-slate-700 hover:border-brand-300",
              )}
            >
              🔖 {saved ? "ذخیره شد" : "ذخیره کسب‌وکار"}
            </button>
          </section>

          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <h2 className="text-sm font-bold text-slate-900">درباره کسب‌وکار</h2>
            <p className="mt-2 text-xs leading-7 text-slate-600">
              {business.description || business.short_description}
            </p>
            <div className="mt-4 rounded-xl bg-slate-50 p-3">
              <p className="text-[11px] text-slate-400">آدرس</p>
              <p className="mt-1 text-xs leading-6 text-slate-700">{business.address}</p>
            </div>
          </section>

          {business.geo && (
            <section className="space-y-2">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-bold text-slate-900">موقعیت روی نقشه</h2>
                {neshanLink && (
                  <a
                    href={neshanLink}
                    target="_blank"
                    rel="noreferrer"
                    className="text-[11px] text-brand-600"
                  >
                    باز کردن در نشان
                  </a>
                )}
              </div>
              <NeshanMap
                center={business.geo}
                markers={mapMarkers}
                zoom={15}
                fitToMarkers
                className="h-56"
              />
            </section>
          )}

          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="text-sm font-bold text-slate-900">نظرات کاربران</h2>
                <p className="mt-1 text-[11px] text-slate-500">
                  ★ {formatRating(business.rating_avg)} از {fa(business.rating_count)} نظر تأییدشده
                </p>
              </div>
              {!business.is_owner &&
                (business.my_review ? (
                  <Badge tone={myReviewBadge(business.my_review).tone}>
                    {myReviewBadge(business.my_review).label}
                  </Badge>
                ) : (
                  <Button size="sm" onClick={requestReview}>
                    ثبت نظر
                  </Button>
                ))}
            </div>

            {business.is_owner ? (
              <p className="mt-4 rounded-xl bg-slate-50 px-3 py-2 text-[11px] leading-5 text-slate-500">
                شما مالک این کسب‌وکار هستید و نمی‌توانید برای آن نظر ثبت کنید.
              </p>
            ) : business.my_review ? (
              <p
                className={
                  business.my_review.is_private
                    ? "mt-4 rounded-xl bg-sky-50 px-3 py-2 text-[11px] leading-5 text-sky-700"
                    : "mt-4 rounded-xl bg-amber-50 px-3 py-2 text-[11px] leading-5 text-amber-800"
                }
              >
                {business.my_review.is_private
                  ? "نظر خصوصی شما ثبت شده و فقط مالک کسب‌وکار آن را می‌بیند."
                  : business.my_review.status === "approved"
                    ? "نظر شما تأیید و منتشر شده است."
                    : business.my_review.status === "rejected"
                      ? "نظر شما توسط مدیر رد شد."
                      : "نظر شما ثبت شده و در انتظار تأیید مدیر است."}
              </p>
            ) : null}

            <div className="mt-4 space-y-3">
              {business.reviews.length === 0 ? (
                <p className="rounded-xl border border-dashed border-slate-200 px-3 py-6 text-center text-xs text-slate-400">
                  هنوز نظر تأییدشده‌ای برای این کسب‌وکار ثبت نشده است.
                </p>
              ) : (
                business.reviews.map((review) => (
                  <article key={review.id} className="rounded-2xl border border-slate-100 bg-slate-50 p-3">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-xs font-bold text-slate-800">
                          {review.author_name || "کاربر نومکس"}
                        </p>
                        <RatingStars rating={review.rating} className="mt-1" />
                      </div>
                      <span className="shrink-0 text-[10px] text-slate-400">
                        {review.created_at ? formatJalali(review.created_at) : ""}
                      </span>
                    </div>
                    {review.text && (
                      <p className="mt-2 whitespace-pre-line text-xs leading-6 text-slate-600">
                        {review.text}
                      </p>
                    )}
                    {review.reply && (
                      <div className="mt-2 rounded-xl bg-white px-3 py-2">
                        <p className="text-[10px] font-bold text-brand-600">پاسخ مالک کسب‌وکار</p>
                        <p className="mt-1 text-[11px] leading-5 text-slate-600">{review.reply}</p>
                      </div>
                    )}
                  </article>
                ))
              )}
            </div>
          </section>
        </div>
      )}

      {business && (
        <>
          <ReviewSheet
            open={reviewOpen}
            businessName={business.name}
            businessSlug={business.slug}
            onClose={() => setReviewOpen(false)}
            onSubmitted={() => {
              void queryClient.invalidateQueries({ queryKey: ["business", slug] });
            }}
          />
          <LoginRequiredSheet
            open={loginPrompt !== null}
            title={loginPrompt === "save" ? "ورود برای ذخیره کسب‌وکار" : "ورود برای ثبت نظر"}
            description={
              loginPrompt === "save"
                ? "برای ذخیره کسب‌وکار در حساب خود، ابتدا وارد شوید یا ثبت‌نام کنید."
                : "برای ثبت امتیاز و نظر برای این کسب‌وکار، ابتدا وارد شوید یا ثبت‌نام کنید."
            }
            next={loginPrompt === "save" ? currentPath : reviewNext}
            onClose={() => setLoginPrompt(null)}
          />
        </>
      )}
    </main>
  );
}
