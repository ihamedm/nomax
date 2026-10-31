import { useEffect, useMemo, useRef, useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button, Spinner } from "@/components/ui/button";
import { Icon } from "@/components/ui/icons";
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
import { BusinessGallery } from "./detail/BusinessGallery";

function PhoneIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M5 4h4l2 5-2.5 1.5a12 12 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2Z" />
    </Icon>
  );
}

function NavigationIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="m3 11 18-8-8 18-2-8-8-2Z" />
    </Icon>
  );
}

function PinIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M20 10c0 6-8 12-8 12S4 16 4 10a8 8 0 1 1 16 0Z" />
      <circle cx="12" cy="10" r="2.5" />
    </Icon>
  );
}

function ClockIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <circle cx="12" cy="12" r="9" />
      <path d="M12 7v5l3 2" />
    </Icon>
  );
}

function ShieldIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <path d="M12 3 4.5 6v5c0 4.5 3.2 8.2 7.5 10 4.3-1.8 7.5-5.5 7.5-10V6L12 3Z" />
      <path d="m9 12 2 2 4-4" />
    </Icon>
  );
}

function InstagramIcon({ className }: { className?: string }) {
  return (
    <Icon className={className}>
      <rect x="3" y="3" width="18" height="18" rx="5" />
      <circle cx="12" cy="12" r="4" />
      <path d="M17.5 6.5h.01" />
    </Icon>
  );
}

function BookmarkIcon({ filled = false }: { filled?: boolean }) {
  return (
    <svg
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className="h-5 w-5"
      aria-hidden
    >
      <path d="M6 4.5A1.5 1.5 0 0 1 7.5 3h9A1.5 1.5 0 0 1 18 4.5V21l-6-4-6 4z" />
    </svg>
  );
}

function myReviewBadge(review: NonNullable<BusinessDetail["my_review"]>) {
  if (review.is_private) return { label: "نظر خصوصی", tone: "sky" as const };
  if (review.status === "approved") return { label: "نظر شما منتشر شد", tone: "brand" as const };
  if (review.status === "rejected") return { label: "نظر رد شد", tone: "rose" as const };
  return { label: "در انتظار تأیید", tone: "amber" as const };
}

function telHref(phone: string | null | undefined) {
  if (!phone) return null;
  return `tel:${phone.startsWith("0") ? phone : `0${phone}`}`;
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

  const photos = useMemo(() => {
    if (!business) return [];
    if (business.images?.length) {
      return [...business.images].sort((a, b) => a.sort_order - b.sort_order);
    }
    return business.profile_image_url
      ? [{ url: business.profile_image_url, is_main: true, sort_order: 0 }]
      : [];
  }, [business]);

  const instagramHandle = business?.instagram?.replace(/^@/, "").replace(/[^A-Za-z0-9._]/g, "");
  const ownerName = business?.owner?.name?.trim() || "مالک نومکس";
  const ownerPhone = business?.owner?.phone?.trim() || null;
  const displayPhone = business?.phone_business?.trim() || ownerPhone;
  const callNumber = telHref(displayPhone);
  const neshanLink = business?.geo
    ? `https://neshan.org/maps/@${business.geo.lat},${business.geo.lng},16z`
    : null;

  return (
    <main className="mx-auto min-h-[100dvh] w-full max-w-3xl pb-16">
      {loading && (
        <div className="flex justify-center py-24 text-brand-600">
          <Spinner />
        </div>
      )}

      {!loading && error && (
        <div className="px-4 py-10 sm:px-6">
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
        <div className="space-y-3 px-4 pb-2 pt-4 sm:px-6">
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

          <section className="overflow-hidden rounded-[28px] border border-slate-200/80 bg-white shadow-[0_20px_60px_-40px_rgba(15,23,42,0.45)]">
            <div className="relative">
              <BusinessGallery
                name={business.name}
                images={photos}
                icon={business.category?.icon}
              />
              <button
                type="button"
                aria-label={saved ? "حذف از ذخیره‌شده‌ها" : "ذخیره کسب‌وکار"}
                aria-pressed={saved}
                title={saved ? "ذخیره شده" : "ذخیره کسب‌وکار"}
                onClick={requestSave}
                disabled={saveMutation.isPending}
                className={cn(
                  "absolute right-3 top-3 z-10 flex h-10 w-10 items-center justify-center rounded-full border shadow-sm backdrop-blur transition disabled:opacity-60",
                  saved
                    ? "border-brand-600 bg-brand-600 text-white"
                    : "border-white/60 bg-white/90 text-slate-700 hover:border-brand-200 hover:text-brand-700",
                )}
              >
                <BookmarkIcon filled={saved} />
              </button>
            </div>

            <div className="px-5 pb-5 pt-4">
              <div className="flex items-start justify-between gap-3">
                <p className="min-w-0 text-[11px] font-medium text-slate-400">
                  {business.category?.icon} {business.category?.name}
                  {business.subcategory ? ` · ${business.subcategory.name}` : ""}
                </p>
                {business.is_owner && (
                  <Link
                    to={`/businesses/${business.id}/edit`}
                    className="shrink-0 text-[11px] font-bold text-brand-600 hover:text-brand-700"
                  >
                    ویرایش پروفایل
                  </Link>
                )}
              </div>

              <h1 className="mt-1.5 text-2xl font-black leading-9 tracking-tight text-slate-900 sm:text-3xl sm:leading-10">
                {business.name}
              </h1>

              <div className="mt-2 flex flex-wrap items-center gap-2 text-xs">
                <span className="inline-flex items-center gap-1 font-bold text-slate-800">
                  <span className="text-amber-500" aria-hidden>
                    ★
                  </span>
                  {business.rating_count > 0
                    ? formatRating(business.rating_avg)
                    : "بدون امتیاز"}
                </span>
                <span className="h-3 w-px bg-slate-200" aria-hidden />
                <span className="text-slate-400">
                  {business.rating_count > 0
                    ? `${fa(business.rating_count)} نظر`
                    : "اولین نظر را ثبت کنید"}
                </span>
                {business.is_verified && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-brand-50 px-2 py-0.5 text-[10px] font-bold text-brand-700">
                    <ShieldIcon className="h-3 w-3" />
                    تأییدشده
                  </span>
                )}
                {business.is_24h && (
                  <span className="inline-flex items-center gap-1 rounded-full bg-amber-50 px-2 py-0.5 text-[10px] font-bold text-amber-700">
                    <ClockIcon className="h-3 w-3" />
                    ۲۴ ساعته
                  </span>
                )}
              </div>

              {business.short_description && (
                <p className="mt-3 text-sm leading-7 text-slate-600">
                  {business.short_description}
                </p>
              )}
            </div>
          </section>

          <section className="grid grid-cols-2 gap-2.5" aria-label="اقدام‌های کسب‌وکار">
            {callNumber ? (
              <a
                href={callNumber}
                className="flex min-h-16 items-center gap-2.5 rounded-2xl bg-brand-600 px-3.5 text-white shadow-[0_12px_30px_-20px_rgba(11,138,92,0.9)] transition hover:bg-brand-700"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-white/15">
                  <PhoneIcon className="h-[18px] w-[18px]" />
                </span>
                <span className="min-w-0 leading-tight">
                  <span className="block text-[13px] font-bold">
                    {business.phone_business ? "تماس با کسب‌وکار" : "تماس با مالک"}
                  </span>
                  <span dir="ltr" className="mt-1 block text-[10px] text-white/70">
                    {formatPhone(displayPhone ?? "")}
                  </span>
                </span>
              </a>
            ) : (
              <span className="flex min-h-16 items-center justify-center rounded-2xl bg-slate-100 px-3 text-center text-[11px] text-slate-400">
                شماره تماس ثبت نشده
              </span>
            )}

            {neshanLink ? (
              <a
                href={neshanLink}
                target="_blank"
                rel="noreferrer"
                className="flex min-h-16 items-center gap-2.5 rounded-2xl border border-slate-200 bg-white px-3.5 text-slate-800 transition hover:border-brand-200 hover:bg-brand-50/30"
              >
                <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-slate-100 text-slate-600">
                  <NavigationIcon className="h-[18px] w-[18px]" />
                </span>
                <span className="min-w-0 leading-tight">
                  <span className="block text-[13px] font-bold">مسیریابی</span>
                  <span className="mt-1 block text-[10px] text-slate-400">در نشان</span>
                </span>
              </a>
            ) : (
              <span className="flex min-h-16 items-center justify-center rounded-2xl bg-slate-100 px-3 text-center text-[11px] text-slate-400">
                موقعیت ثبت نشده
              </span>
            )}
          </section>

          {business.owner && (
            <section className="flex items-center gap-3 rounded-2xl border border-slate-200 bg-white p-3.5">
              <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-full bg-brand-50 text-base font-black text-brand-700">
                {Array.from(ownerName)[0] || "ن"}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[10px] text-slate-400">مالک کسب‌وکار</p>
                <p className="mt-0.5 truncate text-sm font-bold text-slate-900">{ownerName}</p>
              </div>
              {ownerPhone && (
                <a
                  href={telHref(ownerPhone) ?? undefined}
                  aria-label={`تماس با ${ownerName}`}
                  className="inline-flex h-9 shrink-0 items-center gap-1.5 rounded-full bg-slate-50 px-3 text-[11px] font-bold text-slate-700 transition hover:bg-brand-50 hover:text-brand-700"
                >
                  <PhoneIcon className="h-3.5 w-3.5" />
                  <span dir="ltr">{formatPhone(ownerPhone)}</span>
                </a>
              )}
            </section>
          )}

          <section className="rounded-2xl border border-slate-200 bg-white p-5">
            <div className="flex items-center justify-between gap-3">
              <h2 className="text-sm font-bold text-slate-900">درباره کسب‌وکار</h2>
              {instagramHandle && (
                <a
                  href={`https://instagram.com/${instagramHandle}`}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center gap-1 text-[11px] font-bold text-brand-600 hover:text-brand-700"
                >
                  <InstagramIcon className="h-3.5 w-3.5" />
                  اینستاگرام
                </a>
              )}
            </div>
            {business.description && (
              <p className="mt-2 whitespace-pre-line text-xs leading-7 text-slate-600">
                {business.description}
              </p>
            )}
            <div
              className={cn(
                "flex items-start gap-3",
                business.description ? "mt-4 border-t border-slate-100 pt-4" : "mt-4",
              )}
            >
              <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-slate-50 text-slate-500">
                <PinIcon className="h-4 w-4" />
              </span>
              <div className="min-w-0">
                <p className="text-[10px] text-slate-400">آدرس</p>
                <p className="mt-0.5 text-xs leading-6 text-slate-700">{business.address}</p>
              </div>
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
